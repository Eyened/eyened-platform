/** Brush, Eraser and Enhance settings stored per browser; sizes are in image pixels. */
export interface PaintPrefs {
    size2D: number;
    sizeBscan: number;
    hardness: number;
    pressure: number;
}

export const PAINT_DEFAULTS: PaintPrefs = {
    size2D: 4,
    sizeBscan: 4,
    hardness: 0.5,
    pressure: 0.25,
};

export const SIZE_MIN = 0.4;
export const SIZE_MAX = 1000;
/** `[` divides and `]` multiplies the size by this. */
export const SIZE_STEP = 1.25;

/** Graders keep one brush size for 2D images and one for B-scans. */
export function sizeKey(image: { is2D: boolean }): "size2D" | "sizeBscan" {
    return image.is2D ? "size2D" : "sizeBscan";
}

export function clampSize(size: number): number {
    return Math.min(SIZE_MAX, Math.max(SIZE_MIN, size));
}
