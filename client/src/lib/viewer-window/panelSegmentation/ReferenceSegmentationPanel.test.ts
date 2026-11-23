import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { segmentations } from "$lib/data/stores.svelte";
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
const { default: ReferenceSegmentationPanel } = await import(
    "./ReferenceSegmentationPanel.svelte"
);

afterEach(() => {
    cleanup();
    segmentations.clear();
});

describe("ReferenceSegmentationPanel", () => {
    it("the reference picker lists Binary and Questionable segmentations on the viewport's plane only, never the row itself, and a click on a row's text picks it", async () => {
        const target = graderSegmentation(1, ME, "Drusen", {
            data_representation: "Binary",
        });
        segmentations.set(1, target);
        segmentations.set(
            2,
            graderSegmentation(2, ME, "Optic disc", {
                data_representation: "Binary",
            }),
        );
        segmentations.set(
            3,
            graderSegmentation(3, ME, "Optic disc, other plane", {
                data_representation: "Binary",
                sparse_axis: 1,
            }),
        );
        segmentations.set(
            4,
            graderSegmentation(4, ME, "Drusen probability", {
                data_representation: "Probability",
            }),
        );
        const ctx = layersContexts();
        const segmentationItem =
            ctx.segmentationContext.getSegmentationItem(target);
        render(ReferenceSegmentationPanel, {
            props: { segmentation: target, isEditable: true, segmentationItem },
            context: ctx.context,
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Set reference…" }),
        );
        const dialog = await screen.findByRole("dialog", {
            name: "Set reference mask",
        });
        const radios = within(dialog).getAllByRole("radio");
        expect(radios).toHaveLength(1);
        const disc = within(dialog).getByRole("radio", {
            name: "Optic disc [2]",
        });
        const set = within(dialog).getByRole("button", {
            name: "Set reference",
        });
        expect(set).toHaveAttribute("aria-disabled", "true");
        await fireEvent.click(within(dialog).getByText("Optic disc"));
        expect(disc).toBeChecked();
        expect(set).not.toHaveAttribute("aria-disabled");
        await fireEvent.click(set);
        expect(updateSegmentation).toHaveBeenCalledWith(1, {
            reference_segmentation_id: 2,
        });
    });
});
