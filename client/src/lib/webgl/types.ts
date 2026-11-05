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
    /** Scissor box when it is smaller than the viewport, e.g. a strip tile scrolled half out of view. */
    scissor?: RenderBounds;
}
