import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerContext } from "./viewerContext.svelte";

export type RenderMode =
    | "Original"
    | "Luminance"
    | "Contrast enhanced"
    | "Color balanced"
    | "CLAHE"
    | "Sharpened"
    | "Histogram matched"
    | "Red"
    | "Green"
    | "Blue";

export type WindowLevel = { min: number; max: number };

export type PanelName =
    | "Info"
    | "Rendering"
    | "ETDRS"
    | "Registration"
    | "Measure"
    | "Form"
    | "Segmentation"
    | "LayerSegmentation";

export type ToolName =
    | "brush"
    | "polygon"
    | "registration"
    | "ETRDS-grid"
    | "AV nicking tool";

export type Dimension2D = { width: number; height: number };

export type EventName =
    | "pointerdown"
    | "pointerup"
    | "pointermove"
    | "pointerenter"
    | "pointerleave"
    | "wheel"
    | "keydown"
    | "keyup"
    | "dblclick";

export type ViewerModifiers = {
    shift: boolean;
    ctrl: boolean;
    alt: boolean;
    meta: boolean;
};

export type ViewerWheelData = {
    deltaXPx: number;
    deltaYPx: number;
    primaryDeltaPx: number;
    zoomIntent: boolean;
};

export type ViewerDomEvent =
    | PointerEvent
    | KeyboardEvent
    | WheelEvent
    | MouseEvent;

export interface ViewerEvent<
    T extends ViewerDomEvent = ViewerDomEvent,
> {
    event: T;
    viewerContext: ViewerContext;
    cursor: Position2D;
    position: Position2D;
    modifiers: ViewerModifiers;
    wheel?: ViewerWheelData;
}

export interface ViewerEventListener {
    pointerdown?: (arg0: ViewerEvent<PointerEvent>) => void;
    pointerup?: (arg0: ViewerEvent<PointerEvent>) => void;
    pointermove?: (arg0: ViewerEvent<PointerEvent>) => void;
    pointerenter?: (arg0: ViewerEvent<PointerEvent>) => void;
    pointerleave?: (arg0: ViewerEvent<PointerEvent>) => void;
    wheel?: (arg0: ViewerEvent<WheelEvent>) => void;
    keydown?: (arg0: ViewerEvent<KeyboardEvent>) => void;
    keyup?: (arg0: ViewerEvent<KeyboardEvent>) => void;
    dblclick?: (arg0: ViewerEvent<MouseEvent>) => void;
}

export interface Overlay extends ViewerEventListener {
    repaint: (viewerContext: ViewerContext, renderTarget: RenderTarget) => void;
}
