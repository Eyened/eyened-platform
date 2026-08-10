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

    // Single-frame → Image2D, except OPT line/circle scans (need is3D stretch)
    if (depth === 1 && (meta as { x00080060?: string }).x00080060 !== "OPT") {
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
