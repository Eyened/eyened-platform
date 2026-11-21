import type { Position2D } from "$lib/types";
import { AI_GRID, type GridKey } from "./gridLayers.svelte";

/** Fovea to disc edge × the fraction is taken as 3 mm (ETDRS). */
const GRID_UM = 3000;

/** A grid that can size an image, its points already in that image's pixels. */
export interface ScaleGrid {
    key: GridKey;
    fovea: Position2D | null;
    discEdge: Position2D | null;
}

/** What the grader picked in the scale popover for one image. */
export type ScalePick =
    | { kind: "stored" }
    | { kind: "grid"; key: GridKey }
    | { kind: "typed"; x: number; y: number };

/** µm per image pixel on each axis, where it comes from, and the source in use. */
export interface Scale {
    x: number;
    y: number;
    source: string;
    pick: ScalePick;
}

/** µm per pixel from a grid; undefined when a point is missing or both points are on one spot. */
export function gridScale(
    grid: ScaleGrid,
    fraction: number,
): number | undefined {
    if (!grid.fovea || !grid.discEdge) return undefined;
    const px = Math.hypot(
        grid.discEdge.x - grid.fovea.x,
        grid.discEdge.y - grid.fovea.y,
    );
    return px > 0 ? GRID_UM / (fraction * px) : undefined;
}

function fromPick(
    pick: ScalePick,
    stored: { x: number; y: number },
    grids: readonly ScaleGrid[],
    fraction: number,
): Scale | null {
    switch (pick.kind) {
        case "stored":
            return stored.x > 0 && stored.y > 0
                ? { x: stored.x, y: stored.y, source: "stored", pick }
                : null;
        case "typed":
            return pick.x > 0 && pick.y > 0
                ? { x: pick.x, y: pick.y, source: "typed", pick }
                : null;
        case "grid": {
            const grid = grids.find((g) => g.key === pick.key);
            const s = grid && gridScale(grid, fraction);
            if (!s) return null;
            const source =
                pick.key === AI_GRID ? "AI grid" : `from grid ${pick.key}`;
            return { x: s, y: s, source, pick };
        }
    }
}

/** The image's scale: the grader's pick, else the stored resolution, else the only grid shown; null when none gives one. Selecting a grid never changes it. */
export function scaleOf(input: {
    stored: { x: number; y: number };
    grids: readonly ScaleGrid[];
    shown: readonly GridKey[];
    pick: ScalePick | undefined;
    fraction: number;
}): Scale | null {
    const from = (pick: ScalePick) =>
        fromPick(pick, input.stored, input.grids, input.fraction);
    // A pick sticks: when it gives no scale, there is none rather than another source.
    if (input.pick) return from(input.pick);
    const only = input.shown.length === 1 ? input.shown[0] : undefined;
    return (
        from({ kind: "stored" }) ??
        (only !== undefined ? from({ kind: "grid", key: only }) : null)
    );
}

/** "11.20 µm/px", or "9.84 × 9.70 µm/px" when the axes differ. */
export function perPixel(x: number, y: number): string {
    const [a, b] = [x.toFixed(2), y.toFixed(2)];
    return `${a === b ? a : `${a} × ${b}`} µm/px`;
}

/** The scale button's label: the value, then its source. */
export function scaleText(scale: Scale): string {
    return `${perPixel(scale.x, scale.y)} · ${scale.source}`;
}
