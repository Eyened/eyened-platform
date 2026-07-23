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
    meta: any,
): Image2D | VolumeImage {
    const limits = getVolumeLimits(webgl.gl);
    const { width, height, depth } = dimensions;

    if (fitsTexture3D(dimensions, limits)) {
        return new Image3D(instance, webgl, img_id, data, dimensions, meta);
    }

    assertSliceStackFits(dimensions, limits);

    if (depth === 1) {
        return Image2D.fromPixelData(
            instance,
            webgl,
            img_id,
            data,
            dimensions,
            meta,
        );
    }

    return new ImageSliceStack(
        instance,
        webgl,
        img_id,
        data,
        dimensions,
        meta,
    );
}
