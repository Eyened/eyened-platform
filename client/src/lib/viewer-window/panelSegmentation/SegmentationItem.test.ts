import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import {
    graderSegmentation,
    layersContexts,
    modelSegmentation,
    ME,
} from "$lib/layers/testContexts";

vi.mock("./duplicate_utils", async (original) => ({
    ...(await original<typeof import("./duplicate_utils")>()),
    duplicate: vi.fn(async () => undefined),
}));
const { duplicate } = await import("./duplicate_utils");
const { default: SegmentationItem } = await import("./SegmentationItem.svelte");

afterEach(() => {
    cleanup();
    vi.mocked(duplicate).mockClear();
});

function renderRow(ondelete = vi.fn()) {
    const ctx = layersContexts();
    const drusen = graderSegmentation(1, ME, "Drusen v2");
    const other = graderSegmentation(2, ME, "Geographic atrophy");
    ctx.segmentationContext.shownSegmentations.add("grader_segmentation_2");
    const view = render(SegmentationItem, {
        props: { segmentation: drusen, showArea: false, ondelete },
        context: ctx.context,
    });
    return { ...ctx, drusen, other, ondelete, view };
}

describe("SegmentationItem", () => {
    it("the name sets and unsets the current row, which shows its save state in words", async () => {
        const { sync } = renderRow();
        const name = screen.getByRole("button", { name: "Drusen v2" });
        expect(name).toHaveAttribute("aria-pressed", "false");
        await fireEvent.click(name);
        expect(name).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByRole("status")).toHaveTextContent("Saved");
        sync.get(1)!.set("error");
        expect(await screen.findByRole("status")).toHaveTextContent(
            "Couldn't save",
        );
        await fireEvent.click(name);
        expect(name).toHaveAttribute("aria-pressed", "false");
        expect(screen.queryByText("Couldn't save")).toBeNull();
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
        expect(ondelete).toHaveBeenCalledWith(drusen);
        await expectNoAxeViolations(view.container);
    });

    it("the current grader row shows Tags; a current AI row does not", async () => {
        renderRow();
        expect(screen.queryByRole("button", { name: "Edit tags" })).toBeNull();
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen v2" }),
        );
        expect(screen.getByRole("group", { name: "Tags" })).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Edit tags" }),
        ).toBeInTheDocument();
        cleanup();

        const ctx = layersContexts();
        render(SegmentationItem, {
            props: {
                segmentation: modelSegmentation(11, "Drusen AI"),
                showArea: false,
                ondelete: vi.fn(),
            },
            context: ctx.context,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen AI" }),
        );
        expect(screen.queryByRole("button", { name: "Edit tags" })).toBeNull();
    });

    it("a current editable Binary row offers Import, Reference mask and Connected components without a further click; the switch toggles connected components", async () => {
        const ctx = layersContexts();
        const lesion = graderSegmentation(1, ME, "Drusen v2", {
            data_representation: "Binary",
        });
        render(SegmentationItem, {
            props: { segmentation: lesion, showArea: false, ondelete: vi.fn() },
            context: ctx.context,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen v2" }),
        );

        expect(
            screen.getByRole("button", { name: "Import…" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Set reference…" }),
        ).toBeInTheDocument();
        const item = ctx.segmentationContext.getSegmentationItem(lesion);
        const cc = screen.getByRole("switch", {
            name: "Connected components",
        });
        await fireEvent.click(cc);
        expect(ctx.mainViewerContext.applyConnectedComponents.has(item)).toBe(
            true,
        );
        await fireEvent.click(cc);
        expect(ctx.mainViewerContext.applyConnectedComponents.has(item)).toBe(
            false,
        );
    });

    it("Duplicate… opens the Copy and Type options; Create copy closes them and duplicates", async () => {
        const ctx = layersContexts("inst-1", { is3D: true });
        render(SegmentationItem, {
            props: {
                segmentation: graderSegmentation(1, ME, "Drusen v2", {
                    data_representation: "Binary",
                }),
                showArea: false,
                ondelete: vi.fn(),
            },
            context: ctx.context,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen v2" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Duplicate…" }),
        );

        const dialog = await screen.findByRole("dialog", { name: "Duplicate" });
        expect(dialog).toContainElement(
            screen.getByRole("group", { name: "Copy" }),
        );
        expect(dialog).toContainElement(
            screen.getByRole("group", { name: "Type" }),
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
});
