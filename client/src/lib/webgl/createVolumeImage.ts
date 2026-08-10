import type { ImageGET } from "../../types/openapi_types";
import { Image2D } from "./image2D";
import { Image3D } from "./image3D";
import { ImageSliceStack } from "./imageSliceStack";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";
import {
    assertSliceStackFits,
    fitsTexture3D,
    getVolumeLimits,
} from "./volumeLimits";

export type VolumeImage = Image3D | ImageSliceStack;

export function createVolumeImage(
    instance: ImageGET,
    webgl: WebGL,
    img_id: string,
    data: Uint8Array,
    dimensions: Dimensions,
    meta: object,
): Image2D | VolumeImage {
    const limits = getVolumeLimits(webgl.gl);
    const { width, height, depth } = dimensions;

    // Single-frame → Image2D (never depth-1 Image3D / OCT stretch path)
    if (depth === 1) {
        assertSliceStackFits(dimensions, limits);
        console.info(
            `[volume] image ${img_id}: ${width}x${height}x${depth} → Image2D`,
        );
        return Image2D.fromPixelData(
            instance,
            webgl,
            img_id,
            data,
            dimensions,
            meta,
        );
    }

    if (fitsTexture3D(dimensions, limits)) {
        console.info(
            `[volume] image ${img_id}: ${width}x${height}x${depth} → Image3D`,
        );
        return new Image3D(instance, webgl, img_id, data, dimensions, meta);
    }

    assertSliceStackFits(dimensions, limits);
    console.info(
        `[volume] image ${img_id}: ${width}x${height}x${depth} → ImageSliceStack`,
    );
    return new ImageSliceStack(instance, webgl, img_id, data, dimensions, meta);
}
