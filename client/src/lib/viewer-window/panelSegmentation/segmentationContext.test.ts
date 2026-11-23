import { describe, expect, it } from "vitest";
import type { SegmentationGET } from "../../../types/openapi_types";
import { SegmentationContext } from "./segmentationContext.svelte";

const ME = 5;

function context() {
    const image = {
        getOrCreateSegmentationItem: (segmentation: unknown) => ({
            segmentation,
        }),
    };
    return new SegmentationContext("inst-1", 0, {} as never, image as never);
}

describe("SegmentationContext groups", () => {
    it("opens AI and the grader's own group, keeps colleagues closed, and toggles each", () => {
        const ctx = context();
        expect(ctx.isGroupOpen("ai", ME)).toBe(true);
        expect(ctx.isGroupOpen(String(ME), ME)).toBe(true);
        expect(ctx.isGroupOpen("9", ME)).toBe(false);
        ctx.toggleGroup("9", ME);
        ctx.toggleGroup("ai", ME);
        expect(ctx.isGroupOpen("9", ME)).toBe(true);
        expect(ctx.isGroupOpen("ai", ME)).toBe(false);
    });

    it("a new segmentation opens its creator's group and closes the others", () => {
        const ctx = context();
        ctx.toggleGroup("9", ME);
        ctx.activateForDrawing(
            {
                id: 3,
                annotation_type: "grader_segmentation",
                data_representation: "DualBitMask",
            } as SegmentationGET,
            ME,
        );
        expect(ctx.isGroupOpen(String(ME), ME)).toBe(true);
        expect(ctx.isGroupOpen("9", ME)).toBe(false);
        expect(ctx.isGroupOpen("ai", ME)).toBe(false);
    });
});
