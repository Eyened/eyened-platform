
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

export interface RenderTarget {
    left: number;
    bottom: number;
    width: number;
    height: number;
    framebuffer: WebGLFramebuffer | null;
    attachments?: number[];
}
