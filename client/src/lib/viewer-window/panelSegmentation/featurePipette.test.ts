import { describe, expect, it } from "vitest";
import { shouldHandleFeaturePipetteKey } from "./featurePipette";

function setup(isDrawing: boolean) {
    const event = { code: "KeyI", repeat: false, target: null } as never;
    const mainViewerContext = {
        segmentationContext: { isDrawing },
    } as never;
    const viewerContext = {
        active: true,
        activePanels: new Set(["Segmentation"]),
    } as never;
    return () =>
        shouldHandleFeaturePipetteKey(event, mainViewerContext, viewerContext);
}

describe("shouldHandleFeaturePipetteKey", () => {
    it("handles I over the focused Segmentation viewport", () => {
        expect(setup(false)()).toBe(true);
    });

    it("ignores I while a stroke is in progress", () => {
        expect(setup(true)()).toBe(false);
    });
});
