/** Bit for a 1-based subfeature index (matches B-scan MC/ML shaders). */
export function subfeatureBit(featureIndex: number): number {
    return featureIndex > 0
        ? ((1 << (featureIndex - 1)) >>> 0)
        : (1 >>> 0);
}
