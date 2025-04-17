import type { Position2D } from "$lib/types";
import type { ViewerEvent, ViewerEventListener } from "../viewer-utils";

/**
 * Configuration options for ZoomPan behavior
 */
interface ZoomPanOptions {
    scaleSensitivity?: number;
    lineHeightPx?: number;
}

/**
 * Controls zoom and pan functionality in the viewer
 */
export class ZoomPan implements ViewerEventListener {
    // Default values
    private readonly scaleSensitivity: number;
    private readonly LINE_HEIGHT_PX = 16;
    private lastPosition: Position2D | null = null;

    constructor(options?: ZoomPanOptions) {
        this.scaleSensitivity = options?.scaleSensitivity ?? 1.05;
    }

    /**
     * Handles pointer down events to start tracking for potential pan operations
     */
    pointerdown(e: ViewerEvent<PointerEvent>): void {
        this.lastPosition = e.cursor;
    }

    /**
     * Handles pointer up events to end pan tracking
     */
    pointerup(): void {
        this.lastPosition = null;
    }

    /**
     * Handles pointer move events for panning when shift is pressed
     */
    pointermove(e: ViewerEvent<PointerEvent>): void {
        const { event, cursor } = e;
        if (event.shiftKey && this.lastPosition) {
            const { viewerContext } = e;
            viewerContext.pan(this.lastPosition, cursor);
            this.lastPosition = cursor;
        }
    }

    /**
     * Handles wheel events for zooming when shift is pressed
     */
    wheel(e: ViewerEvent<WheelEvent>): void {
        const { viewerContext, event, cursor } = e;

        if (!event.shiftKey) return;

        const zoomFactor = this.calculateZoomFactor(event);
        viewerContext.zoom(cursor.x, cursor.y, zoomFactor);
    }

    /**
     * Calculates the zoom factor based on wheel event details
     */
    private calculateZoomFactor(event: WheelEvent): number {
        let pixelDeltaY = this.normalizeWheelDelta(event);
        const direction = -Math.sign(pixelDeltaY);
        const magnitude = 1 + Math.abs(pixelDeltaY) / 100;
        const f = direction * magnitude;

        return Math.pow(this.scaleSensitivity, f);
    }

    /**
     * Normalizes wheel delta values across different delta modes
     */
    private normalizeWheelDelta(event: WheelEvent): number {
        switch (event.deltaMode) {
            case WheelEvent.DOM_DELTA_LINE:
                return event.deltaY * this.LINE_HEIGHT_PX;
            case WheelEvent.DOM_DELTA_PAGE:
                return event.deltaY * window.innerHeight;
            default: // WheelEvent.DOM_DELTA_PIXEL or unknown
                return event.deltaY;
        }
    }

    /**
     * Handles keyboard events for resetting view
     */
    keydown(e: ViewerEvent<KeyboardEvent>): void {
        const { viewerContext, event } = e;
        if (event.code === 'Escape') {
            viewerContext.initTransform();
        }
    }
}