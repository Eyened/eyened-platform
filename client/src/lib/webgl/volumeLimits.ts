import type { Dimensions } from "./types";

export interface WebGLVolumeLimits {
    maxTexture3DSize: number;
    maxTexture2DSize: number;
    maxArrayTextureLayers: number;
}

export function getVolumeLimits(gl: WebGL2RenderingContext): WebGLVolumeLimits {
    return {
        maxTexture3DSize: gl.getParameter(gl.MAX_3D_TEXTURE_SIZE),
        maxTexture2DSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
        maxArrayTextureLayers: gl.getParameter(gl.MAX_ARRAY_TEXTURE_LAYERS),
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
    dimensions: Pick<Dimensions, "width" | "height" | "depth">,
    limits: WebGLVolumeLimits,
): boolean {
    return (
        dimensions.width <= limits.maxTexture2DSize &&
        dimensions.height <= limits.maxTexture2DSize &&
        dimensions.depth <= limits.maxArrayTextureLayers
    );
}

export function assertSliceStackFits(
    dimensions: Pick<Dimensions, "width" | "height" | "depth">,
    limits: WebGLVolumeLimits,
): void {
    if (fitsSliceStack(dimensions, limits)) {
        return;
    }
    throw new Error(
        `Volume ${dimensions.width}x${dimensions.height}x${dimensions.depth} exceeds ` +
            `2D array limits (MAX_TEXTURE_SIZE=${limits.maxTexture2DSize}, ` +
            `MAX_ARRAY_TEXTURE_LAYERS=${limits.maxArrayTextureLayers})`,
    );
}
