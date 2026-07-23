/** Background class stored in DB; not drawn or listed in the UI. */
export const BACKGROUND_SUBFEATURE_INDEX = 0;

export function isDrawableSubfeatureIndex(index: number): boolean {
    return index > BACKGROUND_SUBFEATURE_INDEX;
}

/** Bit for a 1-based subfeature index (matches B-scan MC/ML shaders). */
export function subfeatureBit(featureIndex: number): number {
    if (!isDrawableSubfeatureIndex(featureIndex)) {
        return 0;
    }
    return (1 << (featureIndex - 1)) >>> 0;
}
