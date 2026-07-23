import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";

export interface WebGLVolumeLimits {
    maxTexture3DSize: number;
    maxTexture2DSize: number;
}

export function getVolumeLimits(gl: WebGL2RenderingContext): WebGLVolumeLimits {
    return {
        maxTexture3DSize: gl.getParameter(gl.MAX_3D_TEXTURE_SIZE),
        maxTexture2DSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
    };
}

export function fitsTexture3D(
    dimensions: Pick<Dimensions, "width" | "height" | "depth">,
    limits: WebGLVolumeLimits,
): boolean {
    const max = limits.maxTexture3DSize;
    return (
        dimensions.width <= max &&
        dimensions.height <= max &&
        dimensions.depth <= max
    );
}

export function fitsSliceStack(
    dimensions: Pick<Dimensions, "width" | "height">,
    limits: WebGLVolumeLimits,
): boolean {
    const max = limits.maxTexture2DSize;
    return dimensions.width <= max && dimensions.height <= max;
}

export function assertSliceStackFits(
    dimensions: Dimensions,
    limits: WebGLVolumeLimits,
): void {
    if (fitsSliceStack(dimensions, limits)) {
        return;
    }
    throw new Error(
        `Volume slice size ${dimensions.width}x${dimensions.height} exceeds ` +
            `MAX_TEXTURE_SIZE (${limits.maxTexture2DSize})`,
    );
}

export function getVolumeLimitsForWebGL(webgl: WebGL): WebGLVolumeLimits {
    return getVolumeLimits(webgl.gl);
}
