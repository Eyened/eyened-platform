import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { segmentations } from "$lib/data/stores.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import {
    graderSegmentation,
    layersContexts,
    ME,
} from "$lib/layers/testContexts";
import SegmentationItem from "./SegmentationItem.svelte";

afterEach(() => {
    cleanup();
    segmentations.clear();
});

function renderRow(ondelete = vi.fn()) {
    const ctx = layersContexts();
    const drusen = graderSegmentation(1, ME, "Drusen v2");
    const other = graderSegmentation(2, ME, "Geographic atrophy");
    segmentations.set(1, drusen);
    segmentations.set(2, other);
    ctx.segmentationContext.shownSegmentations.add("grader_segmentation_2");
    const view = render(SegmentationItem, {
        props: { segmentation: drusen, showArea: false, ondelete },
        context: ctx.context,
    });
    return { ...ctx, drusen, other, ondelete, view };
}

describe("SegmentationItem", () => {
    it("the name selects and unselects the row", async () => {
        renderRow();
        const name = screen.getByRole("button", { name: "Drusen v2" });
        expect(name).toHaveAttribute("aria-pressed", "false");
        await fireEvent.click(name);
        expect(name).toHaveAttribute("aria-pressed", "true");
        await fireEvent.click(name);
        expect(name).toHaveAttribute("aria-pressed", "false");
    });

    it("right-click on the eye shows only this segmentation", async () => {
        const { segmentationContext } = renderRow();
        await fireEvent.contextMenu(
            screen.getByRole("button", { name: "Show" }),
        );
        expect([...segmentationContext.shownSegmentations]).toEqual([
            "grader_segmentation_1",
        ]);
        await fireEvent.click(screen.getByRole("button", { name: "Hide" }));
        expect(segmentationContext.shownSegmentations.size).toBe(0);
    });

    it("Delete hands the segmentation to the section, and the row passes axe", async () => {
        const { ondelete, drusen, view } = renderRow();
        await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
        expect(ondelete).toHaveBeenCalledWith(drusen, expect.any(MouseEvent));
        await expectNoAxeViolations(view.container);
    });

    it("a failed save marks the row Couldn't save until it saves", async () => {
        const { sync } = renderRow();
        expect(screen.queryByText("Couldn't save")).toBeNull();
        sync.get(1)!.set("error");
        expect(await screen.findByText("Couldn't save")).toBeInTheDocument();
        sync.get(1)!.set("synced");
        await waitFor(() =>
            expect(screen.queryByText("Couldn't save")).toBeNull(),
        );
    });
});
