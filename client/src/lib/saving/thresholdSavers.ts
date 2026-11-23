import { updateSegmentation } from "$lib/data/api";
import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { SvelteMap } from "svelte/reactivity";
import { DebouncedSaver } from "./debouncedSaver.svelte";
import type { Saver } from "./saveTracker.svelte";

const keyOf = (s: Segmentation) => `${s.annotation_type}_${s.id}`;

/** One saver per segmentation's threshold; it outlives the slider, which shows only in the segmentation's pane. */
export const thresholdSavers = new SvelteMap<string, DebouncedSaver<number>>();

export function thresholdSaver(
    segmentation: Segmentation,
    imageId: string,
): DebouncedSaver<number> {
    const key = keyOf(segmentation);
    let saver = thresholdSavers.get(key);
    if (!saver) {
        saver = new DebouncedSaver<number>({
            kind: "segmentation",
            group: key,
            target: {
                to: "layers",
                section: "segmentations",
                imageId,
                item: { kind: "segmentation", segmentation },
            },
            delay: 0,
            send: (threshold) =>
                updateSegmentation(segmentation.id, { threshold }),
        });
        thresholdSavers.set(key, saver);
    }
    return saver;
}

/** A segmentation's savers: its B-scans' masks and its threshold. The pane and the row show the worst. */
export function segmentationSavers(item: {
    segmentation: Segmentation;
    savers: Saver[];
}): Saver[] {
    const threshold = thresholdSavers.get(keyOf(item.segmentation));
    return threshold ? [...item.savers, threshold] : item.savers;
}
