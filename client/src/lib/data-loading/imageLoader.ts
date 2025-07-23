import { fsHost } from '$lib/config';
import type { Instance } from '$lib/datamodel/instance.svelte';
import { Image2D } from '$lib/webgl/image2D';
import { Image3D } from '$lib/webgl/image3D';
import type { Dimensions } from '$lib/webgl/types';
import type { WebGL } from '$lib/webgl/webgl';
import { splitTail } from '../utils';

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

    async load(instance: Instance): Promise<LoadedImages> {
        const img_id = `${instance.id}`;
        // Convert to lowercase for case-insensitive comparison
        const extension = instance.datasetIdentifier.toLowerCase().split('.').pop();
        const supportedFormats = ['png', 'jpg', 'jpeg', 'gif', 'webp'];

        if (extension && supportedFormats.includes(extension)) {
            return [await this.loadImage2D(instance, img_id)];

        } else if (instance.datasetIdentifier.endsWith('.binary')) {
            const url = `${fsHost}/${instance.datasetIdentifier}`;
            const meta = await this.loadMeta(url);
            const image = await this.loadBinary3D(instance, url, meta, img_id);
            return this.returnImage3D(image);

        } else if (instance.datasetIdentifier.endsWith('.dcm')) {
            return this.loadDicom(instance, img_id);

        } else if (instance.datasetIdentifier.startsWith('[png_series')) {
            const [pre, base_url] = instance.datasetIdentifier.split(']');
            const [folder, source_id] = splitTail(base_url, '/');
            const meta_url = `${fsHost}/${folder}/metadata.json`;
            const response = await fetch(meta_url);
            const meta = await response.json();
            return this.loadPngSeries(instance, meta, img_id, pre, base_url, source_id);
        } else {
            throw 'unsupported data format';
        }
    }

    async loadPngSeries(instance: Instance, meta: any, img_id: string, pre: string, base_url: string, source_id: string): Promise<LoadedImages> {
        const n_scans = parseInt(pre.split('_')[2]);
        const urls = Array.from({ length: n_scans }, (_, i) => {
            const fileName = `${base_url}_${i}.png`;
            return `${fsHost}/${fileName}`;
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
            console.log('dimensions', dimensions);
            const img3d = new Image3D(instance, this.webgl, img_id, getArrayFromImages(js_images), dimensions!, meta)
            return await this.returnImage3D(img3d);
        }

        throw 'no images found?'
    }

    async returnImage3D(img3d: Image3D): Promise<LoadedImages> {
        if (img3d.depth > this.minBscansForEnface) {
            return [await img3d.createEnfaceProjection(), img3d];
        } else {
            return [img3d];
        }
    }

    async loadImage2D(instance: Instance, img_id: string): Promise<Image2D> {

        const url = `${fsHost}/${instance.datasetIdentifier}`;
        const bitmap = await getImage(url);
        const dimensions = {
            width: bitmap.width,
            height: bitmap.height,
            depth: 1,
            width_mm: instance.resolutionHorizontal ? instance.resolutionHorizontal * bitmap.width : -1,
            height_mm: instance.resolutionVertical ? instance.resolutionVertical * bitmap.height : -1,
            depth_mm: -1
        };
        const meta = undefined;
        return Image2D.fromBitmap(instance, this.webgl, img_id, bitmap, dimensions, meta);
    }

    async loadMeta(url: string): Promise<any> {
        const response = await fetch(url.replace('.binary', '.json'));
        const meta = await response.json();
        return meta;
    }

    async loadBinary3D(instance: Instance, url: string, meta: any, img_id: string): Promise<Image3D> {
        const response = await fetch(url);
        const buffer = await response.arrayBuffer();
        const pixelData = new Uint8Array(buffer);

        const dimensions = {
            width: meta.oct_shape[2],
            height: meta.oct_shape[1],
            depth: meta.oct_shape[0],

            width_mm: meta.resolution[2] * meta.oct_shape[2] / 1000,
            height_mm: meta.resolution[1] * meta.oct_shape[1] / 1000,
            depth_mm: meta.resolution[0] * meta.oct_shape[0] / 1000
        };
        if (instance.scan?.mode == 'Circle-Scan') {
            // this is not correct in the meta file
            dimensions.width_mm = instance.resolutionHorizontal * dimensions.width;
        }
        return new Image3D(instance, this.webgl, img_id, pixelData, dimensions, meta);
    }

    async loadDicom(instance: Instance, img_id: string): Promise<LoadedImages> {
        const url = `${fsHost}/${instance.datasetIdentifier}`;

        const imageId = `wadouri:${url}`;
        const image = await cornerstone.loadImage(imageId);

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
}

async function getImage(url: string): Promise<ImageBitmap> {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const bitmap = await createImageBitmap(blob);
    return bitmap;
}


function toCanvas(img: HTMLImageElement) {
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(img, 0, 0);
    return canvas;
}



// export async function getImage(url: string): Promise<HTMLCanvasElement> {
//     return new Promise((resolve, reject) => {
//         const image = new Image();
//         image.crossOrigin = 'Anonymous';
//         image.onload = () => resolve(toCanvas(image));
//         image.onerror = () => reject(new Error('could not load image'));
//         image.src = url;
//     });
// }


function getArrayFromImages(js_images: HTMLCanvasElement[]): Uint8Array {
    const w = js_images[0].width;
    const h = js_images[0].height;
    const pixelData = new Uint8Array(js_images.length * w * h);
    for (let i = 0; i < js_images.length; i++) {
        const img = js_images[i];
        const ctx = img.getContext('2d')!;
        const imageData = ctx.getImageData(0, 0, w, h);
        const img_data = imageData.data;
        for (let j = 0; j < img_data.length; j += 4) {
            pixelData[i * w * h + j / 4] = img_data[j];
        }
    }
    return pixelData;
}