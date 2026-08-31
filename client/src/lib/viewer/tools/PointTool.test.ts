import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Position2D } from "$lib/types";
import type { ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { PointTool } from "./PointTool.svelte";

vi.mock("svelte-sonner", () => ({
    toast: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}));

const { toast } = await import("svelte-sonner");

function mockViewer(
    overrides: {
        is3D?: boolean;
        image_id?: string;
        index?: number;
    } = {},
): ViewerContext {
    const ctx2d = {
        strokeStyle: "",
        fillStyle: "",
        font: "",
        lineWidth: 0,
        beginPath: vi.fn(),
        arc: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        fill: vi.fn(),
        fillText: vi.fn(),
        strokeRect: vi.fn(),
        fillRect: vi.fn(),
    };
    return {
        image: {
            is3D: overrides.is3D ?? false,
            image_id: overrides.image_id ?? "img1",
            width: 100,
        },
        index: overrides.index ?? 0,
        viewerSize: { width: 100, height: 100 },
        context2D: ctx2d,
        viewerToImageCoordinates: (c: Position2D) => c,
        imageToViewerCoordinates: (c: Position2D) => c,
        claimCursor: vi.fn(),
        resetCursor: vi.fn(),
        setIndex: vi.fn(),
        focusPoint: vi.fn(),
    } as unknown as ViewerContext;
}

function pointerEvent(
    viewerContext: ViewerContext,
    cursor: Position2D,
    extra: Partial<PointerEvent> = {},
): ViewerEvent<PointerEvent> {
    return {
        event: { shiftKey: false, button: 0, ...extra } as PointerEvent,
        viewerContext,
        cursor,
    };
}

function keyEvent(
    viewerContext: ViewerContext,
    cursor: Position2D,
    key: string,
    extra: Partial<KeyboardEvent> = {},
): ViewerEvent<KeyboardEvent> {
    return {
        event: { key, repeat: false, ...extra } as KeyboardEvent,
        viewerContext,
        cursor,
    };
}

describe("PointTool", () => {
    beforeEach(() => {
        vi.mocked(toast.warning).mockClear();
    });

    it("places a point on left click and persists on pointerup", () => {
        const onChange = vi.fn();
        const onPersist = vi.fn();
        const tool = new PointTool({ onChange, onPersist });
        const viewer = mockViewer();

        tool.pointerdown(pointerEvent(viewer, { x: 10, y: 20 }));
        expect(tool.points).toEqual([{ x: 10, y: 20 }]);
        expect(onChange).toHaveBeenCalled();

        tool.pointerup(pointerEvent(viewer, { x: 10, y: 20 }));
        expect(onPersist).toHaveBeenCalledWith([{ x: 10, y: 20 }]);
    });

    it("does not place when canEdit is false", () => {
        const tool = new PointTool({ canEdit: false });
        tool.pointerdown(pointerEvent(mockViewer(), { x: 1, y: 1 }));
        expect(tool.points).toEqual([]);
    });

    it("warns and skips placement when coordinate space rejects the viewer", () => {
        const tool = new PointTool({ coordinateSpace: "enface2d" });
        tool.placeAtCursor(mockViewer({ is3D: true }), { x: 1, y: 1 });
        expect(tool.points).toEqual([]);
        expect(toast.warning).toHaveBeenCalled();
    });

    it("stores a B-scan index on volume viewers", () => {
        const tool = new PointTool({ coordinateSpace: "volume" });
        tool.placeAtCursor(mockViewer({ is3D: true, index: 4 }), {
            x: 2,
            y: 3,
        });
        expect(tool.points[0]).toMatchObject({ x: 2, y: 3, index: 4 });
    });

    it("stores null index on enface _proj for oct space", () => {
        const tool = new PointTool({ coordinateSpace: "oct" });
        tool.placeAtCursor(mockViewer({ image_id: "oct1_proj" }), {
            x: 5,
            y: 6,
        });
        expect(tool.points[0]).toMatchObject({ index: null });
    });

    it("never stores index for enface2d", () => {
        const tool = new PointTool({ coordinateSpace: "enface2d" });
        tool.placeAtCursor(mockViewer(), { x: 1, y: 1 });
        expect(tool.points[0]).toEqual({ x: 1, y: 1 });
    });

    it("places into a fixed slot when placementIndex is set", () => {
        const tool = new PointTool();
        tool.placementIndex = 2;
        tool.placeAtCursor(mockViewer(), { x: 8, y: 9 });
        expect(tool.points[2]).toEqual({ x: 8, y: 9 });
        expect(tool.placementIndex).toBe(2);
    });

    it("drags an existing hit and right-click deletes", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({ onPersist, radius: 16 });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10 }];

        tool.pointerdown(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.pointermove(pointerEvent(viewer, { x: 30, y: 40 }));
        expect(tool.points[0]).toMatchObject({ x: 30, y: 40 });

        tool.pointerup(pointerEvent(viewer, { x: 30, y: 40 }, { button: 2 }));
        expect(tool.points).toEqual([]);
        expect(onPersist).toHaveBeenCalled();
    });

    it("ignores shift-clicks", () => {
        const tool = new PointTool();
        tool.pointerdown(
            pointerEvent(mockViewer(), { x: 1, y: 1 }, { shiftKey: true }),
        );
        expect(tool.points).toEqual([]);
    });

    it("cycles enum extras on C key", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({
            onPersist,
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10, severity: "mild" }];
        tool.pointermove(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.keydown(keyEvent(viewer, { x: 10, y: 10 }, "c"));
        expect(tool.points[0]).toMatchObject({ severity: "severe" });
        expect(onPersist).toHaveBeenCalled();
    });

    it("places into a slot from a shortcut key", () => {
        const tool = new PointTool({
            slotKeys: [{ index: 1, key: "f" }],
        });
        const viewer = mockViewer();
        tool.keydown(keyEvent(viewer, { x: 4, y: 5 }, "F"));
        expect(tool.points[1]).toEqual({ x: 4, y: 5 });
        tool.keyup(keyEvent(viewer, { x: 4, y: 5 }, "F"));
        expect(viewer.resetCursor).toHaveBeenCalled();
    });

    it("focuses a sparse numbered slot on keyup", () => {
        const tool = new PointTool({ sparse: true });
        const viewer = mockViewer({ is3D: true, index: 0 });
        tool.points = [null, { x: 2, y: 3, index: 7 }];
        tool.keyup(keyEvent(viewer, { x: 0, y: 0 }, "2"));
        expect(viewer.setIndex).toHaveBeenCalledWith(7);
        expect(viewer.focusPoint).toHaveBeenCalled();
    });

    it("repaints visible markers including rect and cross styles", () => {
        const viewer = mockViewer();
        const circle = new PointTool({
            slotLabels: ["A"],
            pointStyle: "circle",
        });
        circle.points = [{ x: 1, y: 1 }];
        circle.repaint(viewer, {} as never);
        expect(viewer.context2D.arc).toHaveBeenCalled();

        const rect = new PointTool({ pointStyle: "rect" });
        rect.points = [{ x: 1, y: 1 }];
        rect.repaint(viewer, {} as never);
        expect(viewer.context2D.strokeRect).toHaveBeenCalled();

        const cross = new PointTool({ pointStyle: "cross" });
        cross.points = [{ x: 1, y: 1 }];
        cross.repaint(viewer, {} as never);
        expect(viewer.context2D.lineTo).toHaveBeenCalled();
    });

    it("skips volume points that are on another slice", () => {
        const tool = new PointTool();
        const viewer = mockViewer({ is3D: true, index: 1 });
        tool.points = [{ x: 1, y: 1, index: 9 }];
        tool.pointerdown(pointerEvent(viewer, { x: 1, y: 1 }));
        // Miss: existing point is on slice 9, so this click places a new point.
        expect(tool.points).toHaveLength(2);
    });

    it("replaces the sole point in single cardinality", () => {
        const tool = new PointTool({ cardinality: "single" });
        tool.placeAtCursor(mockViewer(), { x: 1, y: 1 });
        tool.placementIndex = undefined;
        tool.placeAtCursor(mockViewer(), { x: 9, y: 8 });
        expect(tool.points).toEqual([{ x: 9, y: 8 }]);
    });

    it("warns when volume space is used on a 2D viewer", () => {
        const tool = new PointTool({ coordinateSpace: "volume" });
        tool.placeAtCursor(mockViewer({ is3D: false }), { x: 1, y: 1 });
        expect(tool.points).toEqual([]);
        expect(toast.warning).toHaveBeenCalled();
    });

    it("ignores keyboard and pointer when not editable", () => {
        const tool = new PointTool({ canEdit: false });
        const viewer = mockViewer();
        tool.keydown(keyEvent(viewer, { x: 1, y: 1 }, "c"));
        tool.pointerup(pointerEvent(viewer, { x: 1, y: 1 }));
        expect(tool.points).toEqual([]);
        tool.destroy();
    });

    it("labels a non-enum extra on repaint", () => {
        const viewer = mockViewer();
        const tool = new PointTool({ cardinality: "single" });
        tool.points = [{ x: 1, y: 1, note: "fovea" }];
        tool.repaint(viewer, {} as never);
        expect(viewer.context2D.fillText).toHaveBeenCalledWith(
            "fovea",
            expect.any(Number),
            expect.any(Number),
        );
    });
});
