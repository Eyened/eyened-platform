import { createVolumeImage } from "$lib/webgl/createVolumeImage";
import { Image2D } from "$lib/webgl/image2D";
import { Image3D } from "$lib/webgl/image3D";
import { ImageSliceStack } from "$lib/webgl/imageSliceStack";
import type { Dimensions } from "$lib/webgl/types";
import type { WebGL } from "$lib/webgl/webgl";
import type { ImageGET } from "../../types/openapi_types";
import { buildImageDataUrl } from "./imageDataUrl";
import type { ImageLoadProgress } from "./loadProgress";
import { dicomDecodeConcurrency, mapPool } from "./mapPool";
import { loadMhdRawFromEndpoints } from "./mhdLoader";

import * as cornerstone from "cornerstone-core";
import * as cornerstoneWADOImageLoader from "cornerstone-wado-image-loader";
import * as dicomParser from "dicom-parser";

// Configure cornerstone WADO image loader
cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
cornerstoneWADOImageLoader.external.dicomParser = dicomParser;
cornerstoneWADOImageLoader.configure({
    beforeSend: (xhr: XMLHttpRequest) => {
        xhr.setRequestHeader("Accept", "application/dicom");
    },
    useWebWorkers: true,
});
// Do not call webWorkerManager.initialize here: CWIL v4 expects a full
// taskConfiguration (incl. decodeTask) and a bare initialize throws
// "Cannot read properties of undefined (reading 'decodeTask')".
// Workers still start on demand via useWebWorkers; we parallelize frames below.

export type LoadedImages =
    | [Image2D]
    | [Image3D]
    | [ImageSliceStack]
    | [Image2D, Image3D];

export class ImageLoader {
    minBscansForEnface = 5;
    constructor(public readonly webgl: WebGL) {}

    async load(
        instance: ImageGET,
        progress?: ImageLoadProgress,
    ): Promise<LoadedImages> {
        const img_id = `${instance.id}`;
        const imageId = instance.id;
        const dataUrl = this.buildDataUrl(imageId);
        const dataFormat = instance.data_format;
        console.info(
            `[imageLoader] load image ${img_id} format=${dataFormat} ` +
                `rows=${instance.rows} cols=${instance.columns} frames=${instance.nr_of_frames ?? 1}`,
        );
        if (dataFormat === "image/png" || dataFormat === "image/jpeg") {
            const image = await this.loadImage2D(instance, img_id);
            console.info(`[imageLoader] image ${img_id} → Image2D (raster)`);
            return [image];
        } else if (dataFormat === "binary") {
            const meta = await this.loadBinaryMeta(imageId);
            const image = await this.loadBinary3D(
                instance,
                dataUrl,
                img_id,
                meta,
            );
            return this.returnLoadedVolume(image);
        } else if (dataFormat === "dicom") {
            const flowStorageId = angioFlowStorageId(instance);
            if (flowStorageId != null) {
                return this.loadOctaDicom(
                    instance,
                    img_id,
                    imageId,
                    flowStorageId,
                    progress,
                );
            }
            return this.loadDicom(instance, img_id, imageId);
        } else if (dataFormat === "png_series") {
            const meta = await this.loadPngSeriesMeta(imageId);
            return this.loadPngSeries(instance, meta, img_id, imageId);
        } else if (dataFormat === "mhd") {
            return this.loadMhd(instance, img_id, imageId);
        } else {
            throw "unsupported data format";
        }
    }

    async loadPngSeries(
        instance: ImageGET,
        meta: any,
        img_id: string,
        imageId: string,
    ): Promise<LoadedImages> {
        const sourceId = instance.data_source_id;

        const metaImages = meta?.images?.images;
        const image = Array.isArray(metaImages)
            ? (metaImages.find((img: any) => img.source_id == sourceId) ??
              metaImages[0])
            : null;
        const n_scans = image?.contents.length;
        const urls = Array.from({ length: n_scans }, (_, index) => {
            return this.buildDataUrl(imageId, { index });
        });
        const js_images = await Promise.all(urls.map(getImage));

        if (image) {
            const dimensions = {
                width: image.size.width,
                height: image.size.height,
                depth: js_images.length,
                width_mm: image.dimensions_mm.width,
                height_mm: image.dimensions_mm.height,
                depth_mm: image.dimensions_mm.depth,
            };
            if (js_images.length == 1) {
                return [
                    Image2D.fromBitmap(
                        instance,
                        this.webgl,
                        img_id,
                        js_images[0],
                        dimensions,
                        meta,
                    ),
                ];
            }
            const volume = createVolumeImage(
                instance,
                this.webgl,
                img_id,
                getArrayFromImages(js_images),
                dimensions!,
                meta,
            );
            return await this.returnLoadedVolume(volume);
        }

        throw new Error("No image metadata found for png_series");
    }

    async returnLoadedVolume(
        volume: Image2D | Image3D | ImageSliceStack,
    ): Promise<LoadedImages> {
        if (volume instanceof Image2D) {
            console.info(
                `[imageLoader] image ${volume.image_id} loaded as Image2D`,
            );
            return [volume];
        }
        if (volume instanceof ImageSliceStack) {
            console.info(
                `[imageLoader] image ${volume.image_id} loaded as ImageSliceStack ` +
                    `(${volume.width}x${volume.height}x${volume.depth}; no enface path)`,
            );
            return [volume];
        }

        return this.returnImage3D(volume);
    }

    async returnImage3D(img3d: Image3D): Promise<LoadedImages> {
        if (
            img3d.depth > this.minBscansForEnface &&
            img3d.orientation === "axial"
        ) {
            console.info(
                `[imageLoader] image ${img3d.image_id} loaded as Image3D + enface ` +
                    `(${img3d.width}x${img3d.height}x${img3d.depth}, orientation=${img3d.orientation})`,
            );
            return [await img3d.createEnfaceProjection(), img3d];
        } else {
            console.info(
                `[imageLoader] image ${img3d.image_id} loaded as Image3D ` +
                    `(${img3d.width}x${img3d.height}x${img3d.depth}, orientation=${img3d.orientation})`,
            );
            return [img3d];
        }
    }

    async loadImage2D(instance: ImageGET, img_id: string): Promise<Image2D> {
        const imageId = instance.id;
        const url = this.buildDataUrl(imageId);
        const bitmap = await getImage(url);
        const dimensions = {
            width: bitmap.width,
            height: bitmap.height,
            depth: 1,
            width_mm: instance.resolution_horizontal
                ? instance.resolution_horizontal * bitmap.width
                : -1,
            height_mm: instance.resolution_vertical
                ? instance.resolution_vertical * bitmap.height
                : -1,
            depth_mm: -1,
        };
        const meta = undefined;
        return Image2D.fromBitmap(
            instance,
            this.webgl,
            img_id,
            bitmap,
            dimensions,
            meta,
        );
    }

    async loadBinary3D(
        instance: ImageGET,
        url: string,
        img_id: string,
        meta?: any,
    ): Promise<Image2D | Image3D | ImageSliceStack> {
        const response = await fetch(url);
        const buffer = await response.arrayBuffer();
        const pixelData = new Uint8Array(buffer);

        const metaDims =
            meta?.oct_shape && meta?.resolution
                ? {
                      width: meta.oct_shape[2],
                      height: meta.oct_shape[1],
                      depth: meta.oct_shape[0],
                      width_mm: (meta.resolution[2] * meta.oct_shape[2]) / 1000,
                      height_mm:
                          (meta.resolution[1] * meta.oct_shape[1]) / 1000,
                      depth_mm: (meta.resolution[0] * meta.oct_shape[0]) / 1000,
                  }
                : null;

        const dimensions = {
            width: metaDims?.width ?? instance.columns,
            height: metaDims?.height ?? instance.rows,
            depth: metaDims?.depth ?? (instance.nr_of_frames || 1),

            width_mm:
                metaDims?.width_mm ??
                (instance.resolution_horizontal
                    ? instance.resolution_horizontal * instance.columns
                    : -1),
            height_mm:
                metaDims?.height_mm ??
                (instance.resolution_axial
                    ? instance.resolution_axial * instance.rows
                    : -1),
            depth_mm:
                metaDims?.depth_mm ??
                (instance.resolution_vertical
                    ? instance.resolution_vertical *
                      (instance.nr_of_frames || 1)
                    : -1),
        };
        if (instance.scan?.mode == "Circle-Scan") {
            // this is not correct in the meta file
            dimensions.width_mm =
                instance.resolution_horizontal * dimensions.width;
        }
        return createVolumeImage(
            instance,
            this.webgl,
            img_id,
            pixelData,
            dimensions,
            meta ?? {},
        );
    }

    /**
     * Show structural OCT first; attach angio_flow in the background so the
     * viewer is usable while the second J2K volume still unpacks.
     */
    async loadOctaDicom(
        instance: ImageGET,
        img_id: string,
        imageId: string,
        flowStorageId: number,
        progress?: ImageLoadProgress,
    ): Promise<LoadedImages> {
        console.info(
            `[imageLoader] dicom ${img_id}: OCTA structural first, then angio_flow ` +
                `(storage_id=${flowStorageId})`,
        );
        const structural = await this.decodeDicomVolume(
            this.buildDataUrl(imageId),
            img_id,
        );
        const { width, height, depth } = structural.dimensions;
        const expected = width * height * depth;
        if (structural.volume.length !== expected) {
            return this.returnLoadedVolume(
                createVolumeImage(
                    instance,
                    this.webgl,
                    img_id,
                    structural.volume,
                    structural.dimensions,
                    structural.meta,
                ),
            );
        }

        const loaded = await this.returnLoadedVolume(
            createVolumeImage(
                instance,
                this.webgl,
                img_id,
                structural.volume,
                structural.dimensions,
                structural.meta,
            ),
        );
        const volumeImage = loaded.find(
            (img): img is Image3D | ImageSliceStack =>
                img instanceof Image3D || img instanceof ImageSliceStack,
        );

        void this.attachOctaFlowInBackground(
            volumeImage,
            imageId,
            flowStorageId,
            expected,
            { width, height, depth },
            progress,
        );

        return loaded;
    }

    private async attachOctaFlowInBackground(
        volumeImage: Image3D | ImageSliceStack | undefined,
        imageId: string,
        flowStorageId: number,
        expected: number,
        structuralShape: { width: number; height: number; depth: number },
        progress?: ImageLoadProgress,
    ): Promise<void> {
        if (!volumeImage) {
            return;
        }
        try {
            const flow = await this.decodeDicomVolume(
                this.buildDataUrl(imageId, { storage_id: flowStorageId }),
                `${imageId}-flow`,
            );
            const { width: fw, height: fh, depth: fd } = flow.dimensions;
            const { width, height, depth } = structuralShape;
            if (fw !== width || fh !== height || fd !== depth) {
                throw new Error(
                    `OCTA shape mismatch: structural ${width}x${height}x${depth} ` +
                        `vs flow ${fw}x${fh}x${fd}`,
                );
            }
            if (flow.volume.length !== expected) {
                throw new Error(
                    `OCTA flow length ${flow.volume.length} != ${expected}`,
                );
            }
            volumeImage.attachFlow(flow.volume);
            progress?.onFlowReady?.(imageId);
            console.info(
                `[imageLoader] dicom ${imageId}: angio_flow attached`,
            );
        } catch (err) {
            console.error(
                `[imageLoader] dicom ${imageId}: angio_flow load failed`,
                err,
            );
        }
    }

    /**
     * Decode a DICOM at ``url`` into a mono volume (or single-frame pixel buffer).
     */
    async decodeDicomVolume(
        url: string,
        logId: string,
    ): Promise<{
        volume: Uint8Array;
        dimensions: Dimensions;
        meta: any;
        photometricInterpretation?: string;
    }> {
        const dicomImageId = `wadouri:${url}`;
        const image = await cornerstone.loadImage(dicomImageId);
        const ds = image.data;

        const meta: any = dicomParser.explicitDataSetToJS(ds);
        const dimensions = this.extractDimensions(meta);

        const photometricInterpretation = meta.x00280004;
        const transferSyntax = meta.x00020010;
        const { width, height, depth } = dimensions;

        const pixelData = ds.elements.x7fe00010;

        if (pixelData.length === width * height * depth) {
            console.info(
                `[imageLoader] dicom ${logId}: uncompressed pixel data ` +
                    `${width}x${height}x${depth} (transferSyntax=${transferSyntax})`,
            );
            const dicomBytes = ds.byteArray as Uint8Array;
            const volume = dicomBytes.subarray(
                pixelData.dataOffset,
                pixelData.dataOffset + pixelData.length,
            );
            return { volume, dimensions, meta, photometricInterpretation };
        }

        if (depth > 1 || meta.x00080060 === "OPT") {
            // Compressed multi-frame (typically J2K): each frame is a separate
            // decode. Parallelize with a capped pool; dataset fetch is cached by URL.
            const concurrency = dicomDecodeConcurrency();
            console.info(
                `[imageLoader] dicom ${logId}: decoding ${depth} frame(s) via cornerstone ` +
                    `(${width}x${height}, modality=${meta.x00080060}, ` +
                    `transferSyntax=${transferSyntax}, concurrency=${concurrency})`,
            );
            const volume = new Uint8Array(width * height * depth);
            const frameSize = width * height;
            // First loadImage already decoded frame 0 — reuse it.
            volume.set(pixelDataAsUint8(image.getPixelData()), 0);

            const frameIndices = Array.from(
                { length: depth - 1 },
                (_, i) => i + 1,
            );
            await mapPool(frameIndices, concurrency, async (frameIndex) => {
                const frameImage = await cornerstone.loadImage(
                    `wadouri:${url}?frame=${frameIndex}`,
                );
                volume.set(
                    pixelDataAsUint8(frameImage.getPixelData()),
                    frameIndex * frameSize,
                );
            });
            return { volume, dimensions, meta, photometricInterpretation };
        }

        console.info(
            `[imageLoader] dicom ${logId}: single-frame 2D via cornerstone ` +
                `(${width}x${height}, photometric=${photometricInterpretation}, transferSyntax=${transferSyntax})`,
        );
        return {
            volume: pixelDataAsUint8(image.getPixelData()),
            dimensions,
            meta,
            photometricInterpretation,
        };
    }

    async loadDicom(
        instance: ImageGET,
        img_id: string,
        imageId: string,
    ): Promise<LoadedImages> {
        const url = this.buildDataUrl(imageId);
        const decoded = await this.decodeDicomVolume(url, img_id);
        const { volume, dimensions, meta, photometricInterpretation } = decoded;
        const { width, height, depth } = dimensions;

        if (volume.length === width * height * depth) {
            return this.returnLoadedVolume(
                createVolumeImage(
                    instance,
                    this.webgl,
                    img_id,
                    volume,
                    dimensions,
                    meta,
                ),
            );
        }

        if (
            photometricInterpretation === "RGB" ||
            photometricInterpretation === "MONOCHROME2"
        ) {
            return [
                Image2D.fromPixelData(
                    instance,
                    this.webgl,
                    img_id,
                    volume,
                    dimensions,
                    meta,
                ),
            ];
        }

        throw new Error("Unknown DICOM format");
    }

    async loadMhd(
        instance: ImageGET,
        img_id: string,
        imageId: string,
    ): Promise<LoadedImages> {
        const loaded = await loadMhdRawFromEndpoints(
            instance,
            imageId,
            this.buildDataUrl.bind(this),
        );
        if (loaded.dimensions.depth <= 1) {
            return [
                Image2D.fromPixelData(
                    instance,
                    this.webgl,
                    img_id,
                    loaded.pixelData,
                    loaded.dimensions,
                    loaded.meta,
                ),
            ];
        }
        return this.returnLoadedVolume(
            createVolumeImage(
                instance,
                this.webgl,
                img_id,
                loaded.pixelData,
                loaded.dimensions,
                loaded.meta,
            ),
        );
    }

    private extractDimensions(meta: any): Dimensions {
        const width = Number(meta.x00280011); // Rows (width)
        const height = Number(meta.x00280010); // Columns (height)
        const depth = Number(meta.x00280008) || 1; // Number of frames (depth)

        let res_w = -1,
            res_h = -1,
            res_d = -1;

        // x00280030: PixelSpacing
        const pixelSpacing = meta.x00280030?.split("\\").map(Number);
        if (pixelSpacing) {
            [res_h, res_w] = pixelSpacing;
        }

        try {
            // Note: this extracts the values from the first frame
            // Perhaps we should implement an Image2DArray for multi-frame images
            // if the resolution varies between frames (e.g. radial + circular scans)

            // x52009229: Shared Functional Groups Sequence
            const resolutions = meta.x52009229[0].x00289110[0];
            [res_h, res_w] = resolutions.x00280030.split("\\").map(Number);
            // x00180050: Slice Thickness
            res_d = Number(resolutions.x00180050);
        } catch (e) {
            if (depth > 1) {
                console.warn("No depth resolution found in DICOM metadata:", e);
            }
        }

        return {
            width,
            height,
            depth,
            width_mm: width * res_w,
            height_mm: height * res_h,
            depth_mm: depth * res_d,
        };
    }

    private buildDataUrl(
        imageId: string,
        query?: Record<string, string | number | boolean | undefined>,
    ): string {
        return buildImageDataUrl(imageId, query);
    }

    private async loadBinaryMeta(imageId: string): Promise<any> {
        const url = this.buildDataUrl(imageId, { meta: true });
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(
                `Failed to load binary metadata (${response.status})`,
            );
        }
        return await response.json();
    }

    private async loadPngSeriesMeta(imageId: string): Promise<any> {
        const metaUrl = this.buildDataUrl(imageId, { meta: true });
        const response = await fetch(metaUrl);
        if (!response.ok) {
            throw new Error(
                `Failed to load png_series metadata (${response.status})`,
            );
        }
        return await response.json();
    }
}

/** Interim: non-primary storage with Format=angio_flow (future: Role column). */
function angioFlowStorageId(instance: ImageGET): number | null {
    const row = (instance.storages ?? []).find(
        (s) => !s.is_primary && s.format === "angio_flow",
    );
    return row?.id ?? null;
}

function pixelDataAsUint8(pixelData: ArrayLike<number>): Uint8Array {
    return pixelData instanceof Uint8Array
        ? pixelData
        : Uint8Array.from(pixelData);
}

async function getImage(url: string): Promise<ImageBitmap> {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const bitmap = await createImageBitmap(blob);
    return bitmap;
}

// TODO: perhaps this can be optimized (or better: convert [png_series] images to DICOM)
function getArrayFromImages(js_images: ImageBitmap[]): Uint8Array {
    const w = js_images[0].width;
    const h = js_images[0].height;
    const pixelData = new Uint8Array(js_images.length * w * h);
    for (let i = 0; i < js_images.length; i++) {
        const img = js_images[i];

        const ctx = new OffscreenCanvas(img.width, img.height).getContext(
            "2d",
        )!;
        ctx.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(0, 0, img.width, img.height);
        for (let j = 0; j < imageData.data.length; j += 4) {
            pixelData[i * w * h + j / 4] = imageData.data[j];
        }
    }
    return pixelData;
}
