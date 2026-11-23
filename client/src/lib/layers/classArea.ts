import { subfeatureBit } from "$lib/viewer-window/panelSegmentation/subfeatureBits";

/** Pixels per class in one slice: MultiClass pixels equal to the class index, MultiLabel pixels with the class bit set. */
export function classPixelCounts(
    data: ArrayLike<number>,
    multiLabel: boolean,
    indices: readonly number[],
): Map<number, number> {
    const counts = new Map<number, number>(indices.map((i) => [i, 0]));
    if (multiLabel) {
        const bits = indices.map(subfeatureBit);
        for (let p = 0; p < data.length; p++) {
            const value = data[p];
            if (value === 0) continue;
            for (let k = 0; k < indices.length; k++)
                if ((value & bits[k]) !== 0)
                    counts.set(indices[k], counts.get(indices[k])! + 1);
        }
        return counts;
    }
    const perValue = new Uint32Array(Math.max(0, ...indices) + 1);
    for (let p = 0; p < data.length; p++) {
        const value = data[p];
        if (value > 0 && value < perValue.length) perValue[value]++;
    }
    for (const i of indices) counts.set(i, perValue[i]);
    return counts;
}
