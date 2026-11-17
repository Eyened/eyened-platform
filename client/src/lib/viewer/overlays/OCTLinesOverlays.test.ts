import { describe, expect, it, vi } from "vitest";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import type { RenderTarget } from "$lib/webgl/types";
import type { LocalizerMode } from "$lib/workspace/workspaceRules";
import { viewerOf } from "../testViewer";
import { OCTLinesOverlay } from "./OCTLinesOverlays";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

// Five horizontal B-scan lines, 20 image px apart, of one synthetic volume on a synthetic en-face image.
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

/** Repaints at `scale` screen px per image px with the crosshair on B-scan 2 (or none); returns each stroke's width and colour. */
function strokes(mode: LocalizerMode, onVolume = true, scale = 1) {
    const viewer = viewerOf("grey");
    vi.mocked(
        viewer.viewerWindowContext.registration.getPosition,
    ).mockReturnValue(onVolume ? { x: 0, y: 0, index: 2 } : undefined);
    vi.spyOn(viewer, "imageToViewerCoordinates").mockImplementation((p) => ({
        x: p.x * scale,
        y: p.y * scale,
    }));
    const seen: string[] = [];
    const ctx = {
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        stroke: () => seen.push(`${ctx.lineWidth} ${ctx.strokeStyle}`),
        getLineDash: () => [],
        setLineDash: vi.fn(),
        lineWidth: 0,
        strokeStyle: "",
    };
    viewer.context2D = ctx as unknown as CanvasRenderingContext2D;
    new OCTLinesOverlay(lines, () => mode).repaint(viewer, {} as RenderTarget);
    return seen;
}

describe("OCTLinesOverlay", () => {
    it("draws nothing, the cased outline and current line, or that plus every other line", () => {
        expect(strokes("off")).toHaveLength(0);
        expect(strokes("current")).toHaveLength(4);
        expect(strokes("current", false)).toHaveLength(2);
        expect(strokes("all")).toHaveLength(8);
    });

    it("draws other B-scans stronger as the on-screen gap between them widens", () => {
        const other = (scale: number) => strokes("all", true, scale).at(-1);
        expect(other(0.1)).toBe("0.5 rgba(0,255,0,0.2)"); // 2 px gap
        expect(other(0.25)).toBe("1 rgba(0,255,0,0.4)"); // 5 px gap
        expect(other(0.5)).toBe("1 rgba(0,255,0,0.6)"); // 10 px gap
    });
});
