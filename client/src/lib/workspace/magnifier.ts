import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

export const MAGNIFIER_ZOOMS = [2, 3, 4, 6] as const;
export type MagnifierZoom = (typeof MAGNIFIER_ZOOMS)[number];

/** The square view's side, in px. */
export const MAGNIFIER_SIZES = { small: 200, medium: 260, large: 340 } as const;
export type MagnifierSize = keyof typeof MAGNIFIER_SIZES;

export interface Point {
    x: number;
    y: number;
}

/** What the Magnifier remembers per browser. A null place is the start corner. */
export interface MagnifierPrefs {
    on: boolean;
    zoom: MagnifierZoom;
    size: MagnifierSize;
    x: number | null;
    y: number | null;
}

export const MAGNIFIER_DEFAULTS: MagnifierPrefs = {
    on: false,
    zoom: 3,
    size: "medium",
    x: null,
    y: null,
};

/** The viewport the pointer was last over, and where, in image coordinates. */
export interface MagnifierSource {
    viewerContext: ViewerContext;
    mainViewerContext: MainViewerContext;
    /** The viewport's 0-based position; null outside the grid. */
    position: number | null;
    x: number;
    y: number;
    /** False once the pointer has left that viewport. */
    inside: boolean;
}
