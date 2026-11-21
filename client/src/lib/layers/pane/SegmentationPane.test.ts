import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import {
    graderSegmentation,
    layersContexts,
    modelSegmentation,
    ME,
} from "../testContexts";

vi.mock(
    "$lib/viewer-window/panelSegmentation/duplicate_utils",
    async (original) => ({
        ...(await original<
            typeof import("$lib/viewer-window/panelSegmentation/duplicate_utils")
        >()),
        duplicate: vi.fn(async () => undefined),
    }),
);
const { duplicate } = await import(
    "$lib/viewer-window/panelSegmentation/duplicate_utils"
);
const { default: SegmentationPane } = await import("./SegmentationPane.svelte");

afterEach(() => {
    cleanup();
    segmentations.clear();
    modelSegmentations.clear();
    vi.mocked(duplicate).mockClear();
});

/** The pane for one stored segmentation, as the Selected pane shows it. */
function renderPane(
    segmentation: Segmentation,
    over: Parameters<typeof layersContexts>[1] = {},
) {
    const ctx = layersContexts("inst-1", over);
    if (segmentation.annotation_type === "model_segmentation")
        modelSegmentations.set(segmentation.id, segmentation);
    else segmentations.set(segmentation.id, segmentation);
    const item = ctx.segmentationContext.getSegmentationItem(segmentation);
    ctx.segmentationContext.segmentationItem = item;
    render(SegmentationPane, {
        props: { id: "pane-name", item },
        context: ctx.context,
    });
    return { ...ctx, item };
}

describe("SegmentationPane", () => {
    it("names the type and shows the save state in words in its header", async () => {
        const { sync } = renderPane(graderSegmentation(1, ME, "Drusen v2"));
        expect(
            screen.getByText("Segmentation · DualBitMask"),
        ).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Saved");
        sync.get(1)!.set("error");
        expect(await screen.findByRole("status")).toHaveTextContent(
            "Couldn't save",
        );
    });

    it("a probability segmentation has Threshold open and Tags folded; an AI one has no Tags", async () => {
        renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                data_representation: "Probability",
            }),
        );
        expect(
            screen.getByRole("spinbutton", { name: "Threshold" }),
        ).toBeInTheDocument();
        const tags = screen.getByRole("button", { name: "Tags" });
        expect(tags).toHaveAttribute("aria-expanded", "false");
        await fireEvent.click(tags);
        expect(
            screen.getByRole("button", { name: "Edit tags" }),
        ).toBeInTheDocument();
        cleanup();
        renderPane(modelSegmentation(11, "Drusen AI"));
        expect(screen.queryByRole("button", { name: "Tags" })).toBeNull();
    });

    it("an editable Binary segmentation offers Import in the header, and Reference image and Connected components folded; the switch toggles connected components", async () => {
        const { mainViewerContext, item } = renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                data_representation: "Binary",
            }),
        );
        expect(
            screen.getByRole("button", { name: "Import…" }),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Reference image" }),
        );
        expect(
            screen.getByRole("button", { name: "Set reference…" }),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Connected components" }),
        );
        const cc = screen.getByRole("switch", {
            name: "Connected components",
        });
        await fireEvent.click(cc);
        expect(mainViewerContext.applyConnectedComponents.has(item)).toBe(true);
    });

    it("Duplicate… opens the Copy and Type options; Create copy closes them and duplicates", async () => {
        renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                data_representation: "Binary",
            }),
            { is3D: true },
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Duplicate…" }),
        );
        const dialog = await screen.findByRole("dialog", { name: "Duplicate" });
        expect(dialog).toContainElement(
            screen.getByRole("group", { name: "Copy" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Create copy" }),
        );
        expect(duplicate).toHaveBeenCalledOnce();
        await waitFor(() =>
            expect(
                screen.queryByRole("dialog", { name: "Duplicate" }),
            ).toBeNull(),
        );
    });

    it("a tag added in the store shows in the pane", async () => {
        const s = graderSegmentation(1, ME, "Drusen v2");
        renderPane(s);
        await fireEvent.click(screen.getByRole("button", { name: "Tags" }));
        segmentations.set(1, {
            ...s,
            tags: [{ id: 5, name: "Reviewed" }],
        } as never);
        expect(await screen.findByText("Reviewed")).toBeInTheDocument();
    });
});
