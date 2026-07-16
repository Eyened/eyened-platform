import type { Position2D } from "$lib/types";

export type ImageBox = {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
};

/** Normalize drag corners to image-space axis-aligned box (top-left → bottom-right). */
export function imageBoxFromCorners(a: Position2D, b: Position2D): ImageBox {
    const x0 = Math.min(a.x, b.x);
    const x1 = Math.max(a.x, b.x);
    const y0 = Math.min(a.y, b.y);
    const y1 = Math.max(a.y, b.y);
    return { x0, y0, x1, y1 };
}

export function imageBoxWidth(box: ImageBox): number {
    return Math.max(1, Math.round(box.x1 - box.x0));
}

export function imageBoxHeight(box: ImageBox): number {
    return Math.max(1, Math.round(box.y1 - box.y0));
}

/**
 * Segmentation → image matrix mapping seg pixel (0,0) to image (x0,y0)
 * and seg (width,height) to image (x1,y1).
 */
export function projectionMatrixFromBox(
    box: ImageBox,
    segWidth: number,
    segHeight: number,
): number[][] {
    if (!box) {
        throw new Error("projectionMatrixFromBox: invalid image box");
    }
    const w = Math.max(1, segWidth);
    const h = Math.max(1, segHeight);
    const sx = (box.x1 - box.x0) / w;
    const sy = (box.y1 - box.y0) / h;
    return [
        [sx, 0, box.x0],
        [0, sy, box.y0],
        [0, 0, 1],
    ];
}

/** Manual scale + translation (uniform scale on both axes). */
export function projectionMatrixFromScaleTranslate(
    scale: number,
    tx: number,
    ty: number,
): number[][] {
    return [
        [scale, 0, tx],
        [0, scale, ty],
        [0, 0, 1],
    ];
}
