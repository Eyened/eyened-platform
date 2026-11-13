import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { segmentations } from "$lib/data/stores.svelte";
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
});
