import { describe, expect, it, vi } from "vitest";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import type { RenderTarget } from "$lib/webgl/types";
import type { LocalizerMode } from "$lib/workspace/workspaceRules";
import { viewerOf } from "../testViewer";
import { OCTLinesOverlay } from "./OCTLinesOverlays";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

// Five horizontal B-scan lines of one synthetic volume on a synthetic en-face image.
const lines = [0, 1, 2, 3, 4].map(
    (i) =>
        new LinePhotoLocator(
            "img-grey",
            "oct-1",
            { x: 10, y: 10 + i * 20 },
            { x: 110, y: 10 + i * 20 },
            i,
            100,
        ),
);

/** Repaints with the crosshair on B-scan 2 (or none); returns how many paths were stroked. */
function strokes(mode: LocalizerMode, onVolume = true): number {
    const viewer = viewerOf("grey");
    vi.mocked(
        viewer.viewerWindowContext.registration.getPosition,
    ).mockReturnValue(onVolume ? { x: 0, y: 0, index: 2 } : undefined);
    const ctx = {
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        stroke: vi.fn(),
        lineWidth: 0,
        strokeStyle: "",
    };
    viewer.context2D = ctx as unknown as CanvasRenderingContext2D;
    new OCTLinesOverlay(lines, () => mode).repaint(viewer, {} as RenderTarget);
    return ctx.stroke.mock.calls.length;
}

describe("OCTLinesOverlay", () => {
    it("draws nothing, the outline and the current line, or every line", () => {
        expect(strokes("off")).toBe(0);
        expect(strokes("current")).toBe(2);
        expect(strokes("current", false)).toBe(1);
        expect(strokes("all")).toBe(5);
    });
});
