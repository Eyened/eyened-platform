import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
    graderSegmentation,
    layersContexts,
    ME,
} from "$lib/layers/testContexts";

vi.mock("$lib/data/api", async (original) => ({
    ...(await original<typeof import("$lib/data/api")>()),
    updateSegmentation: vi.fn(async () => ({})),
}));
const { updateSegmentation } = await import("$lib/data/api");
const { default: ThresholdSlider } = await import("./ThresholdSlider.svelte");

afterEach(() => {
    cleanup();
    vi.mocked(updateSegmentation).mockClear();
});

function renderThreshold() {
    const ctx = layersContexts();
    const segmentation = graderSegmentation(1, ME, "Drusen", {
        data_representation: "Probability",
    });
    const segmentationItem =
        ctx.segmentationContext.getSegmentationItem(segmentation);
    render(ThresholdSlider, {
        props: { segmentation, segmentationItem },
        context: ctx.context,
    });
    return screen.getByRole("spinbutton", { name: "Threshold" });
}

describe("ThresholdSlider", () => {
    it("a typed threshold is saved for the grader's own row", async () => {
        const own = renderThreshold();
        await fireEvent.input(own, { target: { value: "0.7" } });
        await fireEvent.change(own);
        expect(updateSegmentation).toHaveBeenCalledWith(1, { threshold: 0.7 });
    });
});
