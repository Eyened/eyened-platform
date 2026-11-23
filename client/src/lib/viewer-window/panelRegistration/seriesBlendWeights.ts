/**
 * Weights for a slider that walks a series from the first image to the last.
 * 0 is only the first image. 1 is only the last. In between, two neighbours
 * share the weight and every other image is 0.
 */
export function seriesBlendWeights(position: number, count: number): number[] {
    const weights = Array.from({ length: count }, () => 0);
    if (count <= 0) return weights;
    if (count === 1) {
        weights[0] = 1;
        return weights;
    }
    const t = Math.min(1, Math.max(0, position));
    const span = t * (count - 1);
    let index = Math.floor(span);
    let local = span - index;
    if (index >= count - 1) {
        index = count - 2;
        local = 1;
    }
    weights[index] = 1 - local;
    weights[index + 1] = local;
    return weights;
}
