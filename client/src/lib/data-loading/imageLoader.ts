import { apiUrl } from '$lib/config';
import { Image2D } from '$lib/webgl/image2D';
import { Image3D } from '$lib/webgl/image3D';
import type { Dimensions } from '$lib/webgl/types';
import type { WebGL } from '$lib/webgl/webgl';
import type { ImageGET } from '../../types/openapi_types';

import * as cornerstone from 'cornerstone-core';
import * as cornerstoneWADOImageLoader from 'cornerstone-wado-image-loader';
import * as dicomParser from 'dicom-parser';

// Configure cornerstone WADO image loader
cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
cornerstoneWADOImageLoader.external.dicomParser = dicomParser
cornerstoneWADOImageLoader.configure({
    beforeSend: (xhr: XMLHttpRequest) => {
        xhr.setRequestHeader('Accept', 'application/dicom');
    },
    useWebWorkers: true
});

export type LoadedImages = [Image2D] | [Image3D] | [Image2D, Image3D]

export class ImageLoader {
    minBscansForEnface = 5;
    constructor(public readonly webgl: WebGL) { }

    async load(instance: ImageGET): Promise<LoadedImages> {
        const img_id = `${instance.id}`;
        console.log("load=>", instance);
        const imageId = instance.id;
        const dataUrl = this.buildDataUrl(imageId);
        // Convert to lowercase for case-insensitive comparison
        const dataFormat = instance.data_format;

        if (dataFormat === 'image') {
            return [await this.loadImage2D(instance, img_id)];
        } else if (dataFormat === 'binary') {
            const image = await this.loadBinary3D(instance, dataUrl, img_id);
            return this.returnImage3D(image);

        } else if (dataFormat === 'dicom') {
            return this.loadDicom(instance, img_id, imageId);

        } else if (dataFormat === 'png_series' && (instance.multi_file_count ?? 0) > 1) {
            const source_id = instance.data_source_id ?? '';
            const meta_url = this.buildDataUrl(imageId);
            const response = await fetch(meta_url);
            const meta = await response.json();
            return this.loadPngSeries(instance, meta, img_id, instance.multi_file_count!, source_id, imageId);
        } else {
            throw 'unsupported data format';
        }
    }

    async loadPngSeries(instance: ImageGET, meta: any, img_id: string, n_scans: number, source_id: string, imageId: number | string): Promise<LoadedImages> {
        const urls = Array.from({ length: n_scans }, (_, i) => {
            return this.buildDataUrl(imageId, { index: String(i) });
        });
        const js_images = await Promise.all(urls.map(getImage));

        const image = meta.images.images.find((img: any) => img.source_id == source_id);

        if (image) {
            const dimensions = {
                width: image.size.width,
                height: image.size.height,
                depth: js_images.length,
                width_mm: image.dimensions_mm.width,
                height_mm: image.dimensions_mm.height,
                depth_mm: image.dimensions_mm.depth
            };
            if (js_images.length == 1) {
                return [Image2D.fromBitmap(instance, this.webgl, img_id, js_images[0], dimensions, meta)];
            }
            const img3d = new Image3D(instance, this.webgl, img_id, getArrayFromImages(js_images), dimensions!, meta)
            return await this.returnImage3D(img3d);
        }

        throw 'no images found?'
    }

    async returnImage3D(img3d: Image3D): Promise<LoadedImages> {
        if (img3d.depth > this.minBscansForEnface && img3d.orientation === 'axial') {
            return [await img3d.createEnfaceProjection(), img3d];
        } else {
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
            width_mm: instance.resolution_horizontal ? instance.resolution_horizontal * bitmap.width : -1,
            height_mm: instance.resolution_vertical ? instance.resolution_vertical * bitmap.height : -1,
            depth_mm: -1
        };
        const meta = undefined;
        return Image2D.fromBitmap(instance, this.webgl, img_id, bitmap, dimensions, meta);
    }

    async loadBinary3D(instance: ImageGET, url: string, img_id: string): Promise<Image3D> {
        const response = await fetch(url);
        const buffer = await response.arrayBuffer();
        const pixelData = new Uint8Array(buffer);

        const dimensions = {
            width: instance.columns,
            height: instance.rows,
            depth: instance.nr_of_frames || 1,

            width_mm: instance.resolution_horizontal ? instance.resolution_horizontal * instance.columns : -1,
            height_mm: instance.resolution_vertical ? instance.resolution_vertical * instance.rows : -1,
            depth_mm: instance.resolution_axial ? instance.resolution_axial * (instance.nr_of_frames || 1) : -1
        };
        if (instance.scan?.mode == 'Circle-Scan') {
            // this is not correct in the meta file
            dimensions.width_mm = instance.resolution_horizontal * dimensions.width;
        }
        return new Image3D(instance, this.webgl, img_id, pixelData, dimensions, {});
    }

    async loadDicom(instance: ImageGET, img_id: string, imageId?: number | string): Promise<LoadedImages> {
        const url = this.buildDataUrl(imageId ?? instance.id);

        const dicomImageId = `wadouri:${url}`;
        const image = await cornerstone.loadImage(dicomImageId);

        const meta: any = dicomParser.explicitDataSetToJS(image.data);
        const dimensions = this.extractDimensions(meta);

        const photometricInterpretation = meta.x00280004;
        const { width, height, depth } = dimensions;

        if (depth > 1 || meta.x00080060 === 'OPT') { // 3D OCT
            const volume = new Uint8Array(width * height * depth);
            for (let i = 0; i < depth; i++) {
                const frameImageId = `wadouri:${url}?frame=${i}`;
                const frameImage = await cornerstone.loadImage(frameImageId);
                volume.set(new Uint8Array(frameImage.getPixelData()), i * width * height);
            }
            return this.returnImage3D(new Image3D(instance, this.webgl, img_id, volume, dimensions, meta));
        }

        if (photometricInterpretation === 'RGB' || photometricInterpretation === 'MONOCHROME2') {
            const pixelData = new Uint8Array(image.getPixelData());
            return [Image2D.fromPixelData(instance, this.webgl, img_id, pixelData, dimensions, meta)];
        }

        throw new Error('Unknown DICOM format');
    }

    private extractDimensions(meta: any): Dimensions {
        const width = Number(meta.x00280011);  // Rows (width)
        const height = Number(meta.x00280010); // Columns (height)
        const depth = Number(meta.x00280008) || 1;  // Number of frames (depth)

        let res_w = -1, res_h = -1, res_d = -1;

        // x00280030: PixelSpacing 
        const pixelSpacing = meta.x00280030?.split('\\').map(Number);
        if (pixelSpacing) {
            [res_h, res_w] = pixelSpacing;
        }

        try {
            // Note: this extracts the values from the first frame
            // Perhaps we should implement an Image2DArray for multi-frame images 
            // if the resolution varies between frames (e.g. radial + circular scans)

            // x52009229: Shared Functional Groups Sequence
            const resolutions = meta.x52009229[0].x00289110[0];
            [res_h, res_w] = resolutions.x00280030.split('\\').map(Number);
            // x00180050: Slice Thickness	
            res_d = Number(resolutions.x00180050);
        } catch (e) {
            if (depth > 1) {
                console.warn('No depth resolution found in DICOM metadata:', e);
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

    private buildDataUrl(imageId: number | string, query?: Record<string, string>): string {
        const base = apiUrl?.replace(/\/$/, '') ?? '';
        const url = `${base}/images/${encodeURIComponent(String(imageId))}/data`;
        if (!query) {
            return url;
        }
        const search = new URLSearchParams(query);
        return `${url}?${search.toString()}`;
    }
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
        
        const ctx = new OffscreenCanvas(img.width, img.height).getContext('2d')!;
        ctx.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(0, 0, img.width, img.height);
        for (let j = 0; j < imageData.data.length; j += 4) {
            pixelData[i * w * h + j / 4] = imageData.data[j];
        }
    }
    return pixelData;
}