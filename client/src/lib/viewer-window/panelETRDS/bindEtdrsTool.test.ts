import { afterEach, describe, expect, it, vi } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { Position2D } from "$lib/types";
import type { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        putFormAnnotationValue: vi.fn(async () => {}),
    };
});

const { putFormAnnotationValue } = await import("$lib/data");
const { formAnnotationSavers } = await import(
    "$lib/saving/formAnnotationSavers"
);
const { bindEtdrsTool } = await import("./bindEtdrsTool");

afterEach(() => {
    formAnnotations.clear();
    formAnnotationSavers.clear();
});

const viewer = {
    image: { is2D: true, is3D: false, image_id: "inst-1", width: 100 },
    index: 0,
    active: true,
    viewerSize: { width: 100, height: 100 },
    viewerToImageCoordinates: (c: Position2D) => c,
    imageToViewerCoordinates: (c: Position2D) => c,
    claimCursor: vi.fn(),
    resetCursor: vi.fn(),
    addOverlay: vi.fn(() => vi.fn()),
} as unknown as ViewerContext;

function click(tool: PointTool, at: Position2D) {
    const e = {
        event: { shiftKey: false, button: 0 } as PointerEvent,
        viewerContext: viewer,
        cursor: at,
    } as unknown as Parameters<PointTool["pointerdown"]>[0];
    tool.pointerdown(e);
    tool.pointerup(e);
}

describe("bindEtdrsTool", () => {
    it("a click places the selected slot; Keep grid size takes the disc edge along; each release saves", async () => {
        formAnnotations.set(12, {
            id: 12,
            form_data: { fovea: { x: 10, y: 10 }, disc_edge: { x: 40, y: 10 } },
        } as never);
        let keep = false;
        const { tool } = bindEtdrsTool({
            viewerContext: viewer,
            gridId: 12,
            keepSize: () => keep,
        });
        tool.placementIndex = 0;
        click(tool, { x: 100, y: 100 });
        expect(formAnnotations.get(12)?.form_data).toMatchObject({
            fovea: { x: 100, y: 100 },
            disc_edge: { x: 40, y: 10 },
        });
        keep = true;
        click(tool, { x: 150, y: 100 });
        // The fovea moved 50 px right, so the disc edge did too.
        await vi.waitFor(() =>
            expect(putFormAnnotationValue).toHaveBeenLastCalledWith(
                12,
                expect.objectContaining({
                    fovea: expect.objectContaining({ x: 150, y: 100 }),
                    disc_edge: expect.objectContaining({ x: 90, y: 10 }),
                }),
            ),
        );
    });

    it("another viewport's edit of the grid reaches this tool, so its next save keeps both edits", () => {
        formAnnotations.set(12, {
            id: 12,
            form_data: { fovea: { x: 10, y: 10 }, disc_edge: { x: 40, y: 10 } },
        } as never);
        const a = bindEtdrsTool({
            viewerContext: viewer,
            gridId: 12,
            keepSize: () => false,
        });
        const b = bindEtdrsTool({
            viewerContext: viewer,
            gridId: 12,
            keepSize: () => false,
        });
        a.tool.placementIndex = 0;
        b.tool.placementIndex = 1;
        click(a.tool, { x: 100, y: 100 });
        b.sync(formAnnotations.get(12)?.form_data);
        click(b.tool, { x: 200, y: 200 });
        expect(formAnnotations.get(12)?.form_data).toMatchObject({
            fovea: { x: 100, y: 100 },
            disc_edge: { x: 200, y: 200 },
        });
    });

    it("an earlier save resolving mid-click does not take back the click being made", async () => {
        formAnnotations.set(12, {
            id: 12,
            form_data: { fovea: { x: 10, y: 10 }, disc_edge: { x: 40, y: 10 } },
        } as never);
        const { tool, sync } = bindEtdrsTool({
            viewerContext: viewer,
            gridId: 12,
            keepSize: () => false,
        });
        tool.placementIndex = 0;
        click(tool, { x: 100, y: 100 });
        const firstSaved = vi.mocked(putFormAnnotationValue).mock.lastCall![1];
        tool.placementIndex = 1;
        const e = {
            event: { shiftKey: false, button: 0 } as PointerEvent,
            viewerContext: viewer,
            cursor: { x: 200, y: 200 },
        } as unknown as Parameters<PointTool["pointerdown"]>[0];
        tool.pointerdown(e);
        // The first save resolves: the store takes the saved data back.
        const grid = formAnnotations.get(12)!;
        formAnnotations.set(12, { ...grid, form_data: firstSaved });
        sync(firstSaved);
        tool.pointerup(e);
        expect(formAnnotations.get(12)?.form_data).toMatchObject({
            fovea: { x: 100, y: 100 },
            disc_edge: { x: 200, y: 200 },
        });
        await vi.waitFor(() =>
            expect(putFormAnnotationValue).toHaveBeenLastCalledWith(
                12,
                expect.objectContaining({ disc_edge: { x: 200, y: 200 } }),
            ),
        );
    });
});
