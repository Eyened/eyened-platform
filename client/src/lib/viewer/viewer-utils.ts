import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerContext } from "./viewerContext.svelte";

export type RenderMode = 'Original' | 'Luminance' | 'Contrast enhanced' | 'Color balanced' | 'CLAHE' | 'Sharpened' | 'Histogram matched' | 'Red' | 'Green' | 'Blue';

export type WindowLevel = { min: number; max: number; };

export type PanelName = (
    'Info' |
    'Rendering' |
    'ETDRS' |
    'Registration' |
    'Measure' |
    'Form' |
    'Segmentation' |
    'LayerSegmentation'
);

export type ToolName = 'brush' | 'polygon' | 'registration' | 'ETRDS-grid' | 'AV nicking tool';

export type Dimension2D = { width: number; height: number };

export type EventName =
    | 'pointerdown'
    | 'pointerup'
    | 'pointermove'
    | 'pointerenter'
    | 'pointerleave'
    | 'wheel'
    | 'keydown'
    | 'keyup'
    | 'dblclick';

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

export interface ViewerEvent<T extends PointerEvent | KeyboardEvent | WheelEvent | MouseEvent> {
    event: T,
    viewerContext: ViewerContext,
    cursor: Position2D,
    position: Position2D,
    modifiers: ViewerModifiers,
    wheel?: ViewerWheelData
};

export interface ViewerEventListener {
    pointerdown?: (arg0: ViewerEvent<PointerEvent>) => any,
    pointerup?: (arg0: ViewerEvent<PointerEvent>) => any,
    pointermove?: (arg0: ViewerEvent<PointerEvent>) => any,
    pointerenter?: (arg0: ViewerEvent<PointerEvent>) => any,
    pointerleave?: (arg0: ViewerEvent<PointerEvent>) => any,
    wheel?: (arg0: ViewerEvent<WheelEvent>) => any,
    keydown?: (arg0: ViewerEvent<KeyboardEvent>) => any,
    keyup?: (arg0: ViewerEvent<KeyboardEvent>) => any,
    dblclick?: (arg0: ViewerEvent<MouseEvent>) => any,
}

export interface Overlay extends ViewerEventListener {
    repaint: (viewerContext: ViewerContext, renderTarget: RenderTarget) => void
}