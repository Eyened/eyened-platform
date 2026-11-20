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
        active?: boolean;
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
        strokeText: vi.fn(),
        getLineDash: () => [],
        setLineDash: vi.fn(),
    };
    return {
        image: {
            is3D: overrides.is3D ?? false,
            image_id: overrides.image_id ?? "img1",
            width: 100,
        },
        index: overrides.index ?? 0,
        active: overrides.active ?? true,
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

    it("drags an existing hit; the right button deletes nothing; Del removes the point under the pointer, only with the pointer over this viewport", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({ onPersist, radius: 16 });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10 }];

        tool.pointerdown(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.pointermove(pointerEvent(viewer, { x: 30, y: 40 }));
        tool.pointerup(pointerEvent(viewer, { x: 30, y: 40 }));
        expect(tool.points[0]).toMatchObject({ x: 30, y: 40 });

        tool.pointerup(pointerEvent(viewer, { x: 30, y: 40 }, { button: 2 }));
        tool.keydown(
            keyEvent(mockViewer({ active: false }), { x: 30, y: 40 }, "Delete"),
        );
        tool.keydown(keyEvent(viewer, { x: 90, y: 90 }, "Delete"));
        expect(tool.points).toHaveLength(1);
        onPersist.mockClear();
        tool.keydown(keyEvent(viewer, { x: 30, y: 40 }, "Delete"));
        expect(tool.points).toEqual([]);
        expect(onPersist).toHaveBeenCalledWith([]);
    });

    it("ignores shift-clicks", () => {
        const tool = new PointTool();
        tool.pointerdown(
            pointerEvent(mockViewer(), { x: 1, y: 1 }, { shiftKey: true }),
        );
        expect(tool.points).toEqual([]);
    });

    it("seeds the first required grade on place and leaves an optional grade unset", () => {
        const viewer = mockViewer();
        const required = new PointTool({
            enumExtras: [
                { key: "severity", values: ["mild", "severe"], required: true },
            ],
        });
        required.placeAtCursor(viewer, { x: 1, y: 2 });
        expect(required.points[0]).toEqual({ x: 1, y: 2, severity: "mild" });

        const optional = new PointTool({
            enumExtras: [
                {
                    key: "severity",
                    values: ["mild", "severe"],
                    required: false,
                },
            ],
        });
        optional.placeAtCursor(viewer, { x: 3, y: 4 });
        expect(optional.points[0]).toEqual({ x: 3, y: 4 });
    });

    it("cycles the grade on a click that does not drag", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({
            onPersist,
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10, severity: "mild" }];

        tool.pointerdown(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.pointerup(pointerEvent(viewer, { x: 10, y: 10 }));

        expect(tool.points[0]).toEqual({ x: 10, y: 10, severity: "severe" });
        expect(onPersist).toHaveBeenCalledTimes(1);
    });

    it("cycles a graded point when the press stays inside the drag threshold", () => {
        const tool = new PointTool({
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10, severity: "mild" }];

        tool.pointerdown(pointerEvent(viewer, { x: 14, y: 12 }));
        tool.pointermove(pointerEvent(viewer, { x: 16, y: 13 }));
        tool.pointerup(pointerEvent(viewer, { x: 16, y: 13 }));

        expect(tool.points[0]).toEqual({ x: 10, y: 10, severity: "severe" });
    });

    it("moves a point by the cursor delta once the drag passes the threshold", () => {
        const tool = new PointTool({
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10, severity: "mild" }];

        tool.pointerdown(pointerEvent(viewer, { x: 14, y: 12 }));
        tool.pointermove(pointerEvent(viewer, { x: 20, y: 18 }));
        tool.pointerup(pointerEvent(viewer, { x: 20, y: 18 }));

        expect(tool.points[0]).toEqual({ x: 16, y: 16, severity: "mild" });
    });

    it("treats a short move as a drag when the threshold is zero", () => {
        const tool = new PointTool({
            dragThresholdPx: 0,
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer();
        tool.points = [{ x: 10, y: 10, severity: "mild" }];

        tool.pointerdown(pointerEvent(viewer, { x: 14, y: 12 }));
        tool.pointermove(pointerEvent(viewer, { x: 16, y: 13 }));
        tool.pointerup(pointerEvent(viewer, { x: 16, y: 13 }));

        expect(tool.points[0]).toEqual({ x: 12, y: 11, severity: "mild" });
    });

    it("Ctrl-click or ⌘-click stacks a point on an existing marker without cycling or dragging", () => {
        for (const modifier of [{ ctrlKey: true }, { metaKey: true }]) {
            const onPersist = vi.fn();
            const tool = new PointTool({
                onPersist,
                enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
            });
            const viewer = mockViewer();
            tool.points = [{ x: 10, y: 10, severity: "mild" }];

            tool.pointerdown(pointerEvent(viewer, { x: 10, y: 10 }, modifier));
            tool.pointermove(pointerEvent(viewer, { x: 40, y: 50 }, modifier));
            tool.pointerup(pointerEvent(viewer, { x: 40, y: 50 }, modifier));

            expect(tool.points).toEqual([
                { x: 10, y: 10, severity: "mild" },
                { x: 10, y: 10 },
            ]);
            expect(onPersist).toHaveBeenCalledTimes(1);
        }
    });

    it("does not cycle a grade when the same click places the point", () => {
        const tool = new PointTool({
            enumExtras: [
                { key: "severity", values: ["mild", "severe"], required: true },
            ],
        });
        const viewer = mockViewer();
        tool.pointerdown(pointerEvent(viewer, { x: 4, y: 5 }));
        tool.pointerup(pointerEvent(viewer, { x: 4, y: 5 }));
        expect(tool.points[0]).toEqual({ x: 4, y: 5, severity: "mild" });
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
        tool.points = [{ x: 1, y: 1 }];
        tool.keydown(keyEvent(viewer, { x: 1, y: 1 }, "Delete"));
        tool.pointerdown(pointerEvent(viewer, { x: 50, y: 50 }));
        tool.pointerup(pointerEvent(viewer, { x: 50, y: 50 }));
        expect(tool.points).toEqual([{ x: 1, y: 1 }]);
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

    it("C and digit keys do nothing: a click cycles grades, digits are render presets", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({
            onPersist,
            sparse: true,
            enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
        });
        const viewer = mockViewer({ is3D: true });
        tool.points = [
            { x: 10, y: 10, index: 0, severity: "mild" },
            { x: 2, y: 3, index: 7 },
        ];
        tool.pointermove(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.keydown(keyEvent(viewer, { x: 10, y: 10 }, "c"));
        tool.keyup(keyEvent(viewer, { x: 10, y: 10 }, "2"));
        expect(tool.points[0]).toMatchObject({ severity: "mild" });
        expect(viewer.setIndex).not.toHaveBeenCalled();
        expect(onPersist).not.toHaveBeenCalled();
    });

    it("step goes to the previous or next placed point, skipping gaps and stopping at the ends; it sets the B-scan, centres at 100 % and makes the point current", () => {
        const tool = new PointTool({ sparse: true });
        const viewer = mockViewer({ is3D: true });
        tool.points = [
            { x: 1, y: 2, index: 3 },
            null,
            { x: 5, y: 6, index: 7 },
        ];
        tool.step(1, viewer);
        expect(tool.current).toBe(0);
        tool.step(-1, viewer);
        expect(tool.current).toBe(0);
        tool.step(1, viewer);
        expect(tool.current).toBe(2);
        expect(viewer.setIndex).toHaveBeenLastCalledWith(7);
        // The viewer and the image are both 100 px wide, so 100 % is one image pixel per screen pixel.
        expect(viewer.focusPoint).toHaveBeenLastCalledWith(5, 6, 1);
        tool.step(1, viewer);
        expect(tool.current).toBe(2);
    });

    it("Delete removes the current point, the last placed or stepped one; in a fixed slot, the slot's point", () => {
        const tool = new PointTool({ sparse: true });
        const viewer = mockViewer();
        tool.pointerdown(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.pointerup(pointerEvent(viewer, { x: 10, y: 10 }));
        tool.pointerdown(pointerEvent(viewer, { x: 60, y: 60 }));
        tool.pointerup(pointerEvent(viewer, { x: 60, y: 60 }));
        expect(tool.hasCurrent).toBe(true);
        tool.deleteCurrent();
        expect(tool.points[0]).toEqual({ x: 10, y: 10 });
        expect(tool.points[1] ?? null).toBeNull();
        expect(tool.hasCurrent).toBe(false);

        const slots = new PointTool({ sparse: true });
        slots.points = [
            { x: 1, y: 1 },
            { x: 60, y: 60 },
        ];
        slots.placementIndex = 1;
        slots.deleteCurrent();
        expect(slots.points[0]).toEqual({ x: 1, y: 1 });
        expect(slots.points[1] ?? null).toBeNull();
    });

    it("in a fixed slot, pressing a placed point drags it and keeps the slot", () => {
        const tool = new PointTool({ sparse: true });
        tool.points = [
            { x: 10, y: 10 },
            { x: 60, y: 60 },
        ];
        tool.placementIndex = 0;
        const viewer = mockViewer();
        tool.pointerdown(pointerEvent(viewer, { x: 60, y: 60 }));
        tool.pointermove(pointerEvent(viewer, { x: 80, y: 80 }));
        tool.pointerup(pointerEvent(viewer, { x: 80, y: 80 }));
        expect(tool.points[1]).toMatchObject({ x: 80, y: 80 });
        expect(tool.placementIndex).toBe(0);
    });

    it("in a fixed slot, hold Space places the slot's point at the pointer and follows it until release; not with the pointer elsewhere", () => {
        const onPersist = vi.fn();
        const tool = new PointTool({ sparse: true, onPersist });
        tool.placementIndex = 1;
        const viewer = mockViewer();
        const space = { code: "Space", preventDefault: vi.fn() };
        tool.keydown(
            keyEvent(mockViewer({ active: false }), { x: 5, y: 5 }, " ", space),
        );
        expect(tool.points[1] ?? null).toBeNull();
        tool.keydown(keyEvent(viewer, { x: 5, y: 5 }, " ", space));
        tool.pointermove(pointerEvent(viewer, { x: 20, y: 30 }));
        expect(tool.points[1]).toEqual({ x: 20, y: 30 });
        expect(onPersist).not.toHaveBeenCalled();
        tool.keyup(keyEvent(viewer, { x: 20, y: 30 }, " ", space));
        expect(onPersist).toHaveBeenCalledOnce();
        tool.pointermove(pointerEvent(viewer, { x: 70, y: 70 }));
        expect(tool.points[1]).toEqual({ x: 20, y: 30 });
    });
});
