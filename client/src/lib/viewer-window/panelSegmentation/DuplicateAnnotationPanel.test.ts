import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
    graderSegmentation,
    layersContexts,
    ME,
} from "$lib/layers/testContexts";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";

vi.mock("./duplicate_utils", async (original) => ({
    ...(await original<typeof import("./duplicate_utils")>()),
    duplicate: vi.fn(async () => undefined),
}));
const { duplicate } = await import("./duplicate_utils");
const { default: DuplicateAnnotationPanel } = await import(
    "./DuplicateAnnotationPanel.svelte"
);

afterEach(() => {
    cleanup();
    vi.mocked(duplicate).mockClear();
});

function renderPanel(
    over: Parameters<typeof graderSegmentation>[3],
    is3D: boolean,
) {
    const ctx = layersContexts("inst-1", { is3D });
    const segmentation = graderSegmentation(1, ME, "Drusen", over);
    const segmentationItem =
        ctx.segmentationContext.getSegmentationItem(segmentation);
    return render(DuplicateAnnotationPanel, {
        props: {
            segmentation,
            image: ctx.viewerContext.image as never,
            segmentationItem,
        },
        context: ctx.context,
    });
}

describe("DuplicateAnnotationPanel", () => {
    it("on an OCT the copy covers this B-scan or the volume, in the type picked by name", async () => {
        const { container } = renderPanel(
            { data_representation: "DualBitMask" },
            true,
        );
        expect(
            screen.getByRole("radio", { name: "This B-scan" }),
        ).toBeChecked();
        expect(
            screen.getByRole("radio", { name: "Questionable (Q)" }),
        ).toBeChecked();
        await fireEvent.click(screen.getByRole("radio", { name: "Volume" }));
        await fireEvent.click(
            screen.getByRole("radio", { name: "Binary (B)" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Create copy" }),
        );
        expect(vi.mocked(duplicate).mock.calls[0][5]).toBe(true);
        expect(vi.mocked(duplicate).mock.calls[0][6]).toBe("B");
        await expectNoAxeViolations(container);
    });

    it("a MultiClass copy keeps its type, and a 2D image has no Copy choice", () => {
        renderPanel({ data_representation: "MultiClass" }, false);
        expect(
            screen.getByText("Keeps the MultiClass type."),
        ).toBeInTheDocument();
        expect(screen.queryByRole("group", { name: "Type" })).toBeNull();
        expect(screen.queryByRole("group", { name: "Copy" })).toBeNull();
    });
});
