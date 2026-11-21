import {
    formAnnotations,
    modelSegmentations,
    segmentations,
} from "$lib/data/stores.svelte";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { DistanceLines, Line } from "./distanceLines.svelte";

/** What a viewport's Layers has selected: the item the Selected pane shows and tools edit. */
export type Selected =
    | { kind: "segmentation"; item: SegmentationItem }
    | { kind: "grid"; id: number }
    | { kind: "pointset"; id: number }
    | { kind: "line"; line: Line; lines: DistanceLines };

/** Whether the selected item still exists; a delete in any viewport ends every selection of it. */
function exists(s: Selected): boolean {
    switch (s.kind) {
        case "segmentation": {
            const { id, annotation_type } = s.item.segmentation;
            return annotation_type === "model_segmentation"
                ? modelSegmentations.has(id)
                : segmentations.has(id);
        }
        case "grid":
        case "pointset":
            return formAnnotations.has(s.id);
        case "line":
            return s.lines.lines.includes(s.line);
    }
}

/** One viewport's selection: one item of any layer type, or nothing. */
export class LayerSelection {
    private picked: Selected | null = $state.raw(null);

    /** The selected item; null when nothing is selected or the item was deleted. */
    get value(): Selected | null {
        const p = this.picked;
        return p && exists(p) ? p : null;
    }

    select(selected: Selected | null): void {
        this.picked = selected;
    }

    segmentationItem(): SegmentationItem | undefined {
        const v = this.value;
        return v?.kind === "segmentation" ? v.item : undefined;
    }

    gridId(): number | undefined {
        const v = this.value;
        return v?.kind === "grid" ? v.id : undefined;
    }

    pointsetId(): number | undefined {
        const v = this.value;
        return v?.kind === "pointset" ? v.id : undefined;
    }

    line(): Line | undefined {
        const v = this.value;
        return v?.kind === "line" ? v.line : undefined;
    }
}
