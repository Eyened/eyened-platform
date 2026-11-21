import { afterEach, describe, expect, it } from "vitest";
import { formAnnotations, segmentations } from "$lib/data/stores.svelte";
import { DistanceLines, Line } from "./distanceLines.svelte";
import { LayerSelection } from "./layerSelection.svelte";
import { graderSegmentation, layersContexts, ME } from "./testContexts";

afterEach(() => {
    segmentations.clear();
    formAnnotations.clear();
});

describe("LayerSelection", () => {
    it("holds one item of any type: selecting a grid ends the segmentation selection", () => {
        const { segmentationContext, selection } = layersContexts();
        const s = graderSegmentation(1, ME, "Drusen v2");
        segmentations.set(1, s);
        formAnnotations.set(11, { id: 11 } as never);
        segmentationContext.toggleActive(
            segmentationContext.getSegmentationItem(s),
        );
        expect(segmentationContext.segmentationItem).toBeDefined();
        selection.select({ kind: "grid", id: 11 });
        expect(segmentationContext.segmentationItem).toBeUndefined();
        expect(selection.gridId()).toBe(11);
    });

    it("reads as nothing once its item is deleted", () => {
        const selection = new LayerSelection();
        formAnnotations.set(20, { id: 20 } as never);
        selection.select({ kind: "pointset", id: 20 });
        formAnnotations.delete(20);
        expect(selection.value).toBeNull();

        const lines = new DistanceLines();
        const line = new Line({ x: 0, y: 0 }, { x: 3, y: 4 }, 0);
        lines.add(line);
        selection.select({ kind: "line", line, lines });
        lines.remove(line);
        expect(selection.line()).toBeUndefined();
    });
});
