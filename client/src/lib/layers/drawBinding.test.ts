import { describe, expect, it } from "vitest";
import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { drawBinding } from "./drawBinding";

const ME = 5;

function segmentation(over: Record<string, unknown> = {}): Segmentation {
    return {
        id: 1,
        annotation_type: "grader_segmentation",
        data_representation: "MultiClass",
        creator: { id: ME },
        feature: {
            name: "AMD grading",
            subfeatures: [
                { index: 1, name: "Drusen" },
                { index: 2, name: "Pigment" },
            ],
        },
        ...over,
    } as unknown as Segmentation;
}

const mine = (s: Segmentation) =>
    s.annotation_type !== "model_segmentation" &&
    (s as { creator: { id: number } }).creator.id === ME;

describe("drawBinding", () => {
    it("names the segmentation and the class it draws when it can be drawn in", () => {
        expect(
            drawBinding({
                segmentation: segmentation(),
                activeIndices: 1,
                toolId: "brush",
                canEdit: mine,
            }),
        ).toEqual({
            name: { segmentation: "AMD grading", feature: "Drusen" },
            reason: null,
        });
    });

    it("gives the reason it can't, in order: none, model, another grader's, Enhance on a non-probability one", () => {
        const reason = (s: Segmentation | null, toolId = "brush") =>
            drawBinding({
                segmentation: s,
                activeIndices: [],
                toolId: toolId as never,
                canEdit: mine,
            }).reason;
        expect(reason(null)).toBe("Select a segmentation to draw");
        expect(
            reason(segmentation({ annotation_type: "model_segmentation" })),
        ).toBe(
            "This model segmentation can't be edited. Duplicate it to edit.",
        );
        expect(reason(segmentation({ creator: { id: 9 } }))).toBe(
            "Another grader's segmentation can't be edited. Duplicate it to edit.",
        );
        expect(
            reason(segmentation({ data_representation: "Binary" }), "enhance"),
        ).toBe(
            "Enhance works on probability segmentations only. Choose one in Segmentations.",
        );
        expect(
            reason(
                segmentation({ data_representation: "Probability" }),
                "enhance",
            ),
        ).toBeNull();
    });
});
