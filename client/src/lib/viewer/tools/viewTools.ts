import type { Matrix } from "$lib/matrix";
import type { Position2D } from "$lib/types";
import type { ToolId } from "$lib/workspace/tools/registry";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";

/** Zoom factor per pixel of vertical drag. */
const ZOOM_PER_PX = 1.01;
/** Viewer pixels a press may move and still count as a click. */
const CLICK_PX = 4;

/** Shift+drag pans with any tool, so a tool leaves Shift presses and other buttons alone. */
const isToolPress = (e: ViewerEvent<PointerEvent>) =>
    e.event.button === 0 && !e.modifiers.shift;

/** BIR zoom: drag down zooms in, drag up zooms out, about the press point. A click does nothing. */
export class ZoomTool implements Overlay {
    private start: { at: Position2D; transform: Matrix } | null = null;

    pointerdown(e: ViewerEvent<PointerEvent>) {
        if (!isToolPress(e)) return;
        this.start = { at: e.cursor, transform: e.viewerContext.transform };
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (!this.start) return;
        const { at, transform } = this.start;
        const factor = Math.pow(ZOOM_PER_PX, e.cursor.y - at.y);
        e.viewerContext.transform = transform.zoom(at.x, at.y, factor);
    }

    pointerup() {
        this.start = null;
    }

    repaint(viewerContext: ViewerContext) {
        viewerContext.claimCursor("zoom-in", CursorPriority.Tool);
    }
}

/** Drag pans; a click centres the clicked point. */
export class PanTool implements Overlay {
    private down: Position2D | null = null;
    private last: Position2D | null = null;
    private dragging = false;

    pointerdown(e: ViewerEvent<PointerEvent>) {
        if (!isToolPress(e)) return;
        this.down = this.last = e.cursor;
        this.dragging = false;
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (!this.down || !this.last) return;
        const moved = Math.hypot(
            e.cursor.x - this.down.x,
            e.cursor.y - this.down.y,
        );
        if (!this.dragging && moved < CLICK_PX) return;
        this.dragging = true;
        e.viewerContext.pan(this.last, e.cursor);
        this.last = e.cursor;
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        if (this.down && !this.dragging) {
            const { width, height } = e.viewerContext.viewerSize;
            e.viewerContext.pan(this.down, { x: width / 2, y: height / 2 });
        }
        this.down = this.last = null;
        this.dragging = false;
    }

    repaint(viewerContext: ViewerContext) {
        if (this.dragging)
            viewerContext.claimCursor("grabbing", CursorPriority.Drag);
        else viewerContext.claimCursor("grab", CursorPriority.Tool);
    }
}

/** BIR Cross-hair: a click or drag sets the shared crosshair; hover does not while it is armed. */
export class CrosshairTool implements Overlay {
    private pressed = false;

    pointerdown(e: ViewerEvent<PointerEvent>) {
        if (!isToolPress(e)) return;
        this.pressed = true;
        this.set(e);
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (this.pressed) this.set(e);
    }

    pointerup() {
        this.pressed = false;
    }

    private set(e: ViewerEvent<PointerEvent>) {
        const viewer = e.viewerContext;
        if (viewer.isStripTile) return;
        viewer.registration.setPosition(viewer.image.image_id, {
            ...e.position,
            index: viewer.index,
        });
    }

    repaint(viewerContext: ViewerContext) {
        viewerContext.claimCursor("crosshair", CursorPriority.Tool);
    }
}

/** The overlay for an armed view tool; null for No tool and for tools built elsewhere. */
export function createViewTool(id: ToolId | null): Overlay | null {
    switch (id) {
        case "zoom":
            return new ZoomTool();
        case "pan":
            return new PanTool();
        case "crosshair":
            return new CrosshairTool();
        default:
            return null;
    }
}
