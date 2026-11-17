import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import {
    formAnnotations,
    formSchemasByName,
    segmentations,
} from "$lib/data/stores.svelte";
import { Line } from "$lib/viewer/tools/Measure.svelte";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import { workspaceWith } from "$lib/workspace/testUtils";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import { graderSegmentation, layersContexts, ME } from "./testContexts";

vi.mock("$lib/viewer-window/panelSegmentation/DrawingTools.svelte", () => ({
    default: () => {},
}));
vi.mock(
    "$lib/viewer-window/panelSegmentation/NewSegmentationRegion.svelte",
    () => ({ default: () => {} }),
);

const { default: LayersPanel } = await import("./LayersPanel.svelte");

afterEach(() => {
    cleanup();
    segmentations.clear();
    formAnnotations.clear();
    formSchemasByName.delete(BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID);
    localStorage.clear();
});

function attach(ws: Workspace, position: number, instanceId: string) {
    const ctx = layersContexts(instanceId);
    ws.attachViewport(position, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            viewerContext: ctx.viewerContext as never,
            mainViewerContext: ctx.mainViewerContext as never,
            grids: ctx.grids,
            measure: ctx.measure,
        },
    });
    return ctx;
}

function renderPanel(ws: Workspace, hide: string[] = []) {
    const ctx = layersContexts();
    const context = new Map(ctx.context);
    context.set("workspace", ws);
    context.set("taskContext", {
        task: { task_definition: { config: { layout: { hide } } } },
    });
    return render(LayersPanel, {
        props: { subtitle: "Viewport 1 · test", shown: true },
        context,
    });
}

describe("LayersPanel", () => {
    it("lists the selected viewport's segmentations and follows the selection", async () => {
        segmentations.set(
            1,
            graderSegmentation(1, ME, "Drusen v2", {
                image_id: "inst-a",
            } as never),
        );
        segmentations.set(
            2,
            graderSegmentation(2, ME, "Geographic atrophy", {
                image_id: "inst-b",
            } as never),
        );
        const ws = workspaceWith(2);
        attach(ws, 0, "inst-a");
        attach(ws, 1, "inst-b");
        renderPanel(ws);
        expect(
            screen.getByRole("button", { name: "Drusen v2" }),
        ).toBeInTheDocument();
        ws.select(1);
        expect(
            await screen.findByRole("button", { name: "Geographic atrophy" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Drusen v2" })).toBeNull();
    });

    it("says No layers for a slot with no image and when the task hides every section", () => {
        const ws = workspaceWith(1, { layout: "2x1" });
        attach(ws, 0, "inst-a");
        ws.select(1);
        const first = renderPanel(ws);
        expect(screen.getByText("No layers")).toBeInTheDocument();
        first.unmount();
        ws.select(0);
        renderPanel(ws, ["Segmentation", "ETDRS", "Registration", "Measure"]);
        expect(screen.getByText("No layers")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: /Segmentations/ }),
        ).toBeNull();
    });

    it("does not say No layers while the slot's image is still loading", () => {
        renderPanel(workspaceWith(1));
        expect(screen.queryByText("No layers")).toBeNull();
    });

    it("keeps a viewport's grids, current grid, armed slot, radius fraction and lines while another is selected", async () => {
        const name = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;
        formSchemasByName.set(name, { id: 3, name } as never);
        formAnnotations.set(11, {
            id: 11,
            form_schema_id: 3,
            image_id: "inst-a",
            annotation_type: "grader_form",
            sub_task_id: null,
            creator: { id: ME, name: `Grader ${ME}` },
            form_data: {},
        } as never);
        const ws = workspaceWith(2);
        const a = attach(ws, 0, "inst-a");
        attach(ws, 1, "inst-b");
        a.measure.lines.add(new Line({ x: 0, y: 0 }, { x: 3, y: 4 }, 0));
        renderPanel(ws);
        await fireEvent.click(
            screen.getByRole("button", { name: "ETDRS grids 1" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Distance lines 1" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "ETDRS grid, Grader 5" }),
        );
        // Arm Disc edge the way the d key does, through the tool, so only the section's save keeps it.
        const tool = vi
            .mocked(a.viewerContext.addOverlay as ReturnType<typeof vi.fn>)
            .mock.calls.map(([overlay]) => overlay)
            .find((overlay) => overlay instanceof PointTool) as PointTool;
        tool.placementIndex = 1;
        const fraction = screen.getByLabelText("Radius fraction");
        await fireEvent.input(fraction, { target: { value: "0.9" } });
        await fireEvent.change(fraction);

        ws.select(1);
        await tick();
        expect(screen.queryByText(/^Line 1/)).toBeNull();
        ws.select(0);

        expect(
            await screen.findByRole("button", { name: "ETDRS grid, Grader 5" }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(
            screen.getByRole("button", { name: /^Disc edge \(d\)/ }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByLabelText("Radius fraction")).toHaveValue(0.9);
        expect(screen.getByText(/^Line 1 ·/)).toBeInTheDocument();
        expect(a.grids.isShown(11)).toBe(true);
    });
});
