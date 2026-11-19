import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

import { viewerOf, type ImageKind } from "$lib/viewer/testViewer";
import type { EventName } from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { ProbabilityMask } from "$lib/webgl/mask.svelte";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { bindDrawTool } from "./bindDrawTool";
import { SegmentationContext } from "./segmentationContext.svelte";

/** A 2D context whose every method is a no-op. */
const fake2d = new Proxy(
    { canvas: {} },
    {
        get: (target, prop) =>
            prop in target ? target[prop as "canvas"] : vi.fn(),
    },
);

type DrawId = "brush" | "eraser" | "polygon" | "enhance";

function setup(toolId: DrawId, editable = true, kind: ImageKind = "colour") {
    const workspace = new Workspace();
    const viewerContext = viewerOf(kind, { workspace });
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(
        fake2d as never,
    );
    const segmentationContext = new SegmentationContext(
        "inst-1",
        0,
        { viewState: workspace } as never,
        viewerContext.image as never,
    );
    const draw = vi.spyOn(segmentationContext, "draw").mockResolvedValue();
    vi.spyOn(segmentationContext, "getCtx").mockReturnValue(fake2d as never);
    workspace.attachViewport(0, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            viewerContext,
            mainViewerContext: { segmentationContext },
        } as never,
    });
    workspace.arm(toolId);
    bindDrawTool({
        toolId,
        editable,
        viewerContext,
        segmentationContext,
        workspace,
        report: vi.fn(),
    });
    return { workspace, viewerContext, segmentationContext, draw };
}

function send(
    viewerContext: ViewerContext,
    name: EventName,
    event: Record<string, unknown> = {},
    extra: Record<string, unknown> = {},
) {
    viewerContext.forwardEvent(name, {
        event: {
            button: 0,
            key: "",
            code: "",
            repeat: false,
            ctrlKey: false,
            metaKey: false,
            altKey: false,
            shiftKey: false,
            preventDefault: () => {},
            ...event,
        },
        viewerContext,
        cursor: { x: 10, y: 10 },
        position: { x: 10, y: 10 },
        modifiers: { shift: false, ctrl: false, alt: false, meta: false },
        ...extra,
    });
}

function stroke(viewerContext: ViewerContext) {
    send(viewerContext, "pointerdown");
    send(viewerContext, "pointermove");
    send(viewerContext, "pointerup");
}

const SPACE = { key: " ", code: "Space" };
const ESC = { key: "Escape", code: "Escape" };

describe("bindDrawTool", () => {
    beforeEach(() => {
        vi.stubGlobal(
            "Path2D",
            class {
                ellipse() {}
                moveTo() {}
                lineTo() {}
            },
        );
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        localStorage.clear();
    });

    it("writes a Brush stroke only in a viewport that can take it", () => {
        const blocked = setup("brush", false);
        stroke(blocked.viewerContext);
        expect(blocked.draw).not.toHaveBeenCalled();
        const open = setup("brush");
        stroke(open.viewerContext);
        expect(open.draw).toHaveBeenCalledWith(
            expect.anything(),
            "paint",
            open.viewerContext.index,
        );
    });

    it("Eraser erases with the left button; the right button writes nothing", () => {
        const { viewerContext, draw } = setup("eraser");
        send(viewerContext, "pointerdown", { button: 2 });
        send(viewerContext, "pointerup", { button: 2 });
        expect(draw).not.toHaveBeenCalled();
        stroke(viewerContext);
        expect(draw).toHaveBeenCalledWith(
            expect.anything(),
            "erase",
            viewerContext.index,
        );
    });

    it("Esc drops a stroke and keeps the view; losing focus writes the stroke", () => {
        const { viewerContext, draw } = setup("brush");
        viewerContext.zoom(10, 10, 3);
        const view = viewerContext.transform;
        send(viewerContext, "pointerdown");
        send(viewerContext, "pointermove");
        send(viewerContext, "keydown", ESC);
        send(viewerContext, "pointerup");
        expect(draw).not.toHaveBeenCalled();
        expect(viewerContext.transform).toEqual(view);
        send(viewerContext, "pointerdown");
        send(viewerContext, "blur");
        expect(draw).toHaveBeenCalledTimes(1);
    });

    it("Esc ends an Enhance stroke and takes it back", async () => {
        const { viewerContext, segmentationContext } = setup("enhance");
        const mask = Object.assign(Object.create(ProbabilityMask.prototype), {
            drawEnhance: vi.fn(),
        });
        const item = {
            segmentation: { image_projection_matrix: null },
            getSegmentationState: () => ({ mask }),
            draw: vi.fn().mockResolvedValue(undefined),
            undo: vi.fn().mockResolvedValue(undefined),
        };
        segmentationContext.segmentationItem = item as never;
        send(viewerContext, "pointerdown");
        send(viewerContext, "keydown", ESC);
        await vi.waitFor(() =>
            expect(item.undo).toHaveBeenCalledWith(viewerContext.index),
        );
        expect(item.draw).toHaveBeenCalledTimes(1);
        expect(item.draw.mock.invocationCallOrder[0]).toBeLessThan(
            item.undo.mock.invocationCallOrder[0],
        );
    });

    it("holding Space paints only while the pointer is over the viewport", () => {
        const { viewerContext, draw } = setup("brush");
        send(viewerContext, "pointermove");
        viewerContext.active = false;
        send(viewerContext, "keydown", SPACE);
        send(viewerContext, "keyup", SPACE);
        expect(draw).not.toHaveBeenCalled();
        viewerContext.active = true;
        send(viewerContext, "keydown", SPACE);
        send(viewerContext, "pointermove");
        send(viewerContext, "keyup", SPACE);
        expect(draw).toHaveBeenCalledTimes(1);
    });

    it("the wheel steps B-scans with Brush armed, but not during a stroke", () => {
        const { viewerContext } = setup("brush", true, "bscan");
        const wheel = () =>
            send(
                viewerContext,
                "wheel",
                {},
                {
                    wheel: { zoomIntent: false, primaryDeltaPx: 100 },
                },
            );
        wheel();
        expect(viewerContext.index).toBe(65);
        send(viewerContext, "pointerdown");
        wheel();
        send(viewerContext, "pointerup");
        expect(viewerContext.index).toBe(65);
        wheel();
        expect(viewerContext.index).toBe(66);
    });

    it("a digit picks the render preset with Brush armed and leaves the brush size", () => {
        const { viewerContext, workspace } = setup("brush");
        send(viewerContext, "keydown", { key: "2", code: "Digit2" });
        expect(viewerContext.renderMode).toBe("Contrast enhanced");
        expect(workspace.paint.size2D).toBe(4);
    });
});
