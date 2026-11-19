import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ViewerContext } from "../viewerContext.svelte";
import { PolygonTool } from "./Polygon";
import { SetBrushRadiusTool } from "./setBrushRadius";

type Stroke = { width: number; color: string; dash: number[]; path: unknown };

/** A 2D context that records the line style in force at every stroke. */
function recordingCtx() {
    const strokes: Stroke[] = [];
    let dash: number[] = [];
    const saved: number[][] = [];
    const ctx = {
        lineWidth: 1,
        strokeStyle: "",
        fillStyle: "",
        save: () => saved.push(dash),
        restore: () => {
            dash = saved.pop() ?? [];
        },
        setLineDash: (d: number[]) => (dash = d),
        fill: () => {},
        stroke(path: unknown) {
            strokes.push({
                width: ctx.lineWidth,
                color: String(ctx.strokeStyle),
                dash,
                path,
            });
        },
    };
    return { ctx, strokes };
}

function fakeViewer(ctx: unknown) {
    return {
        context2D: ctx,
        aspectRatio: 1,
        image: { is2D: true },
        imageToViewerCoordinates: (p: { x: number; y: number }) => p,
        claimCursor: vi.fn(),
    } as unknown as ViewerContext;
}

const WHITE = "white";

describe("cased cursor drawing", () => {
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
    afterEach(() => vi.unstubAllGlobals());

    function brush(dashed: boolean) {
        const { ctx, strokes } = recordingCtx();
        const viewerContext = fakeViewer(ctx);
        const tool = new SetBrushRadiusTool(
            viewerContext,
            { paint: { size2D: 4 } } as never,
            () => dashed,
        );
        tool.repaint(viewerContext);
        return { strokes, viewerContext };
    }

    it("draws the outline and a centre cross, each as a 3 px dark casing under a 1 px white line", () => {
        const { strokes } = brush(false);
        expect(strokes.map((s) => [s.width, s.color === WHITE])).toEqual([
            [3, false],
            [1, true],
            [3, false],
            [1, true],
        ]);
        expect(strokes[0].color).toMatch(/^rgba\(0, 0, 0/);
    });

    it("dashes the outline while removing, never the cross", () => {
        const { strokes } = brush(true);
        expect(strokes[0].dash).toEqual([4, 3]);
        expect(strokes[1].dash).toEqual([4, 3]);
        expect(strokes[2].dash).toEqual([]);
        expect(strokes[3].dash).toEqual([]);
        expect(brush(false).strokes[1].dash).toEqual([]);
    });

    it("the Polygon lasso is cased, its closing edge dashed, and the cursor a crosshair", () => {
        const { ctx, strokes } = recordingCtx();
        const viewerContext = fakeViewer(ctx);
        const tool = new PolygonTool({
            viewerContext,
            segmentationContext: {} as never,
            view: { paint: {} as never, remove: false, setSize: vi.fn() },
            report: vi.fn(),
        });
        tool.currentPoints = [
            { x: 0, y: 0 },
            { x: 10, y: 0 },
            { x: 10, y: 10 },
        ];
        vi.spyOn(
            tool as unknown as { segmentationToViewer: () => unknown },
            "segmentationToViewer",
        ).mockImplementation(((p: unknown) => p) as never);
        tool.repaint(viewerContext, {} as never);
        expect(strokes.map((s) => [s.width, s.dash])).toEqual([
            [3, []],
            [1, []],
            [3, [5, 5]],
            [1, [5, 5]],
        ]);
        expect(viewerContext.claimCursor).toHaveBeenCalledWith(
            "crosshair",
            expect.anything(),
        );
    });
});
