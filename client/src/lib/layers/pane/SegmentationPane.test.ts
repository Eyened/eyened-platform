import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
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
    it("names the type with the list's group and shows the save state; a failed save has Retry, which sends again; an AI one has no save state", async () => {
        const { sync, item } = renderPane(
            graderSegmentation(1, ME, "Drusen v2"),
        );
        expect(screen.getByText("Segmentation · Mine")).toBeInTheDocument();
        expect(screen.getByText("Saved")).toBeInTheDocument();
        sync.get(1)!.set("error");
        await fireEvent.click(
            await screen.findByRole("button", { name: "Retry" }),
        );
        expect(vi.mocked(item.savers[0].flush)).toHaveBeenCalled();
        cleanup();
        renderPane(modelSegmentation(11, "Drusen AI"));
        expect(screen.getByText("Segmentation · AI")).toBeInTheDocument();
        expect(screen.queryByText("Saved")).toBeNull();
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
        for (const name of ["Reference image None", "Connected components"]) {
            expect(screen.getByRole("button", { name })).toHaveAttribute(
                "aria-expanded",
                "false",
            );
        }
        await fireEvent.click(
            screen.getByRole("button", { name: "Reference image None" }),
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

    it("Duplicate on a 3-D Binary row opens a menu; Volume › As Probability copies the volume as Probability", async () => {
        renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                data_representation: "Binary",
            }),
            { is3D: true },
        );
        const trigger = screen.getByRole("button", { name: "Duplicate" });
        expect(trigger).toHaveAttribute("aria-haspopup", "menu");
        await fireEvent.keyDown(trigger, { key: "Enter" });
        const volume = await screen.findByRole("group", { name: "Volume" });
        await fireEvent.click(
            within(volume).getByRole("menuitem", { name: "As Probability" }),
        );
        expect(duplicate).toHaveBeenCalledOnce();
        const args = vi.mocked(duplicate).mock.calls[0];
        expect(args[5]).toBe(true);
        expect(args[6]).toBe("P");
    });

    it("a 2-D MultiClass row has no Duplicate menu; Duplicate copies straight away", async () => {
        renderPane(
            graderSegmentation(1, ME, "Layers", {
                data_representation: "MultiClass",
            }),
        );
        const button = screen.getByRole("button", { name: "Duplicate" });
        expect(button).not.toHaveAttribute("aria-haspopup");
        await fireEvent.click(button);
        expect(duplicate).toHaveBeenCalledOnce();
        expect(vi.mocked(duplicate).mock.calls[0][5]).toBe(false);
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
        expect(
            screen.getByRole("button", { name: "Tags 1" }),
        ).toBeInTheDocument();
    });

    it("Reference image's title says whose reference it is: Drusen · Mine for yours, a colleague's name for theirs", () => {
        segmentations.set(2, graderSegmentation(2, ME, "Drusen"));
        renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                reference_segmentation_id: 2,
            }),
        );
        expect(
            screen.getByRole("button", {
                name: "Reference image Drusen · Mine",
            }),
        ).toBeInTheDocument();
        cleanup();
        segmentations.set(3, graderSegmentation(3, 7, "Drusen"));
        renderPane(
            graderSegmentation(1, ME, "Drusen v2", {
                reference_segmentation_id: 3,
            }),
        );
        expect(
            screen.getByRole("button", {
                name: "Reference image Drusen · Grader 7",
            }),
        ).toBeInTheDocument();
    });
});
