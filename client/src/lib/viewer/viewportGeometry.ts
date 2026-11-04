import type { Matrix } from "$lib/matrix";

type Size = { width: number; height: number };

export interface Box {
    left: number;
    top: number;
    width: number;
    height: number;
}

const EPSILON = 1e-6;

export function sameTransform(a: Matrix, b: Matrix): boolean {
    return (["a", "b", "c", "d", "e", "f"] as const).every(
        (k) => Math.abs(a[k] - b[k]) < EPSILON,
    );
}

/** A resized viewer keeps the image point at its centre and its scale. */
export function keepViewOnResize(
    transform: Matrix,
    from: Size,
    to: Size,
): Matrix {
    return transform.pan(
        { x: from.width / 2, y: from.height / 2 },
        { x: to.width / 2, y: to.height / 2 },
    );
}

export function sameBox(a: Box, b: Box): boolean {
    return (
        a.left === b.left &&
        a.top === b.top &&
        a.width === b.width &&
        a.height === b.height
    );
}

/** The part of `box` inside `clip`, or null when none is. */
export function clipBox(box: Box, clip: Box): Box | null {
    const left = Math.max(box.left, clip.left);
    const top = Math.max(box.top, clip.top);
    const right = Math.min(box.left + box.width, clip.left + clip.width);
    const bottom = Math.min(box.top + box.height, clip.top + clip.height);
    if (right <= left || bottom <= top) return null;
    return { left, top, width: right - left, height: bottom - top };
}
