import { describe, expect, it, vi } from "vitest";
import type { RenderTarget } from "$lib/webgl/types";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { viewerOf } from "../testViewer";
import type { ViewerContext } from "../viewerContext.svelte";
import { CursorOverlay } from "./CursorOverlay";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

/** Repaints the overlay with the crosshair on a slice; returns how many crosshairs were stroked. */
function strokes(viewer: ViewerContext, index: number): number {
    vi.mocked(
        viewer.viewerWindowContext.registration.getPosition,
    ).mockReturnValue({ x: 5, y: 5, index });
    const ctx = {
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        lineWidth: 0,
        strokeStyle: "",
    };
    viewer.context2D = ctx as unknown as CanvasRenderingContext2D;
    new CursorOverlay().repaint(viewer, {} as RenderTarget);
    return ctx.stroke.mock.calls.length;
}

describe("CursorOverlay", () => {
    it("hides the crosshair on a locked B-scan while it is on another slice", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("bscan", { workspace });
        workspace.setLocked("img-bscan", true);
        expect(strokes(viewer, 64)).toBe(1);
        expect(strokes(viewer, 70)).toBe(0);
    });

    it("draws the crosshair under the pointer only while Cross-hair is armed", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("grey", { workspace });
        viewer.active = true;
        expect(strokes(viewer, 0)).toBe(0);
        workspace.arm("crosshair");
        expect(strokes(viewer, 0)).toBe(1);
    });

    it("draws none on a strip tile while Crosshair tracking is off", () => {
        const workspace = new Workspace();
        const tile = viewerOf("grey", { workspace, tile: true });
        expect(strokes(tile, 0)).toBe(1);
        workspace.stripTracking = false;
        expect(strokes(tile, 0)).toBe(0);
    });
});
