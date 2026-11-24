import { describe, expect, it, vi } from "vitest";
import type { GlobalContext } from "$lib/data/globalContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { FeatureGET } from "../../../types/openapi_types";
import type { SegmentationContext } from "./segmentationContext.svelte";
import { createSegmentationFromDialog } from "./createSegmentationHelpers";

vi.mock("$lib/data", () => ({
    createSegmentationFrom: vi.fn(async () => ({ id: 1 })),
}));

const { createSegmentationFrom } = await import("$lib/data");

describe("createSegmentationFromDialog", () => {
    it.each(["MultiLabel", "MultiClass"] as const)(
        "saves a %s segmentation inside the set",
        async (type) => {
            await createSegmentationFromDialog(
                { user: { id: 5 } } as GlobalContext,
                {
                    activateForDrawing: vi.fn(),
                } as unknown as SegmentationContext,
                {
                    image: { depth: 1 } as AbstractImage,
                    axis: 0,
                    feature: { id: 3 } as FeatureGET,
                    subtaskId: 42,
                    type,
                    mode: "full",
                    segWidth: 4,
                    segHeight: 4,
                },
            );

            expect(
                vi.mocked(createSegmentationFrom).mock.calls.at(-1)?.[6],
            ).toBe(42);
        },
    );
});
