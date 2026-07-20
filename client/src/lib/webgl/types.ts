export interface Dimensions {
    width: number;
    height: number;
    depth: number;
    width_mm: number;
    height_mm: number;
    depth_mm: number;
}

export type RenderBounds = {
    left: number;
    bottom: number;
    width: number;
    height: number;
};

export type ShaderUniformValue =
    | number
    | boolean
    | WebGLTexture
    | Int32Array
    | Uint32Array
    | Float32Array
    | readonly number[];

export type ShaderUniforms = Record<string, ShaderUniformValue>;

export interface RenderTarget {
    left: number;
    bottom: number;
    width: number;
    height: number;
    framebuffer: WebGLFramebuffer | null;
    attachments?: number[];
}
