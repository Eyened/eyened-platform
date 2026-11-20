import { describe, expect, it, vi } from "vitest";
import {
    DistanceLines,
    lengthText,
    Line,
} from "$lib/layers/distanceLines.svelte";
import type { Position2D } from "$lib/types";
import type { ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { MeasureTool } from "./Measure.svelte";

function viewer(active = true): ViewerContext {
    return {
        index: 0,
        active,
        viewerToImageCoordinates: (c: Position2D) => c,
        imageToViewerCoordinates: (c: Position2D) => c,
        claimCursor: vi.fn(),
    } as unknown as ViewerContext;
}

function pointer(
    v: ViewerContext,
    cursor: Position2D,
    extra: Partial<PointerEvent> = {},
): ViewerEvent<PointerEvent> {
    return {
        event: { shiftKey: false, button: 0, ...extra } as PointerEvent,
        viewerContext: v,
        cursor,
    } as unknown as ViewerEvent<PointerEvent>;
}

function key(v: ViewerContext, cursor: Position2D, k: string) {
    return {
        event: { key: k } as KeyboardEvent,
        viewerContext: v,
        cursor,
    } as unknown as ViewerEvent<KeyboardEvent>;
}

/** Press and release at one spot. */
function click(
    tool: MeasureTool,
    v: ViewerContext,
    at: Position2D,
    extra: Partial<PointerEvent> = {},
) {
    tool.pointerdown(pointer(v, at, extra));
    tool.pointerup(pointer(v, at, extra));
}

describe("MeasureTool", () => {
    it("click the start, click the end makes a line; the right button and an unarmed tool do nothing", () => {
        const lines = new DistanceLines();
        let armed = false;
        const tool = new MeasureTool(lines, () => null, () => armed);
        const v = viewer();
        click(tool, v, { x: 10, y: 10 });
        armed = true;
        click(tool, v, { x: 10, y: 10 }, { button: 2 });
        expect(lines.lines).toHaveLength(0);
        click(tool, v, { x: 10, y: 10 });
        tool.pointermove(pointer(v, { x: 40, y: 50 }));
        expect(lines.lines[0].end).toEqual({ x: 40, y: 50 });
        click(tool, v, { x: 40, y: 50 });
        tool.pointermove(pointer(v, { x: 90, y: 90 }));
        expect(lines.lines).toHaveLength(1);
        expect(lines.lines[0].end).toEqual({ x: 40, y: 50 });
        expect(lines.current).toBe(lines.lines[0]);
    });

    it("drags an end to move it; Del removes the line under the pointer, not over empty image or with the pointer elsewhere", () => {
        const lines = new DistanceLines();
        lines.add(new Line({ x: 0, y: 0 }, { x: 30, y: 40 }, 0));
        const tool = new MeasureTool(lines, () => null, () => true);
        const v = viewer();
        tool.pointermove(pointer(v, { x: 30, y: 40 }));
        tool.pointerdown(pointer(v, { x: 30, y: 40 }));
        tool.pointermove(pointer(v, { x: 60, y: 80 }));
        tool.pointerup(pointer(v, { x: 60, y: 80 }));
        expect(lines.lines[0].end).toEqual({ x: 60, y: 80 });
        tool.keydown(key(v, { x: 200, y: 200 }, "Delete"));
        tool.keydown(key(viewer(false), { x: 0, y: 0 }, "Delete"));
        expect(lines.lines).toHaveLength(1);
        tool.keydown(key(v, { x: 0, y: 0 }, "Backspace"));
        expect(lines.lines).toHaveLength(0);
    });
});

describe("lengthText", () => {
    it("measures in px without a scale", () => {
        const line = new Line({ x: 0, y: 0 }, { x: 30, y: 40 }, 0);
        expect(lengthText(line, null)).toBe("50 px");
    });
});
