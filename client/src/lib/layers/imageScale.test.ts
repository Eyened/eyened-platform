import { describe, expect, it } from "vitest";
import { AI_GRID } from "./gridLayers.svelte";
import { scaleOf, type ScaleGrid } from "./imageScale";

const NONE = { x: -1, y: -1 };
const STORED = { x: 11.2, y: 11.2 };
// Fraction 1, so fovea to disc edge is 3 mm: 100 px gives 30 µm/px, 200 px 15, 300 px 10.
const grid = (key: ScaleGrid["key"], px: number | null): ScaleGrid => ({
    key,
    fovea: { x: 0, y: 0 },
    discEdge: px === null ? null : { x: px, y: 0 },
});
const GRIDS = [
    grid(1, 100),
    grid(2, 200),
    grid(AI_GRID, 300),
    grid(3, null),
    grid(4, 0),
];
const scale = (over: Partial<Parameters<typeof scaleOf>[0]>) =>
    scaleOf({
        stored: NONE,
        grids: GRIDS,
        currentId: undefined,
        shown: [],
        pick: undefined,
        fraction: 1,
        ...over,
    });
const value = (s: ReturnType<typeof scaleOf>) => s && [s.x, s.source];

describe("scaleOf", () => {
    it("takes the stored resolution, else the current grid, else the only grid shown, else none", () => {
        expect(value(scale({ stored: STORED, currentId: 1 }))).toEqual([
            11.2,
            "stored",
        ]);
        expect(value(scale({ currentId: 1, shown: [1, 2] }))).toEqual([
            30,
            "from grid 1",
        ]);
        expect(value(scale({ shown: [2] }))).toEqual([15, "from grid 2"]);
        expect(value(scale({ shown: [AI_GRID] }))).toEqual([10, "AI grid"]);
        expect(scale({ shown: [1, 2] })).toBeNull();
    });

    it("skips a grid missing a point or with both points on one spot, so a scale is never Infinity", () => {
        expect(scale({ currentId: 3, shown: [3] })).toBeNull();
        expect(scale({ currentId: 4, shown: [4] })).toBeNull();
    });

    it("a pick overrides the default and sticks: a picked grid missing a point gives no scale, not the default", () => {
        expect(
            value(scale({ stored: STORED, pick: { kind: "grid", key: 2 } })),
        ).toEqual([15, "from grid 2"]);
        expect(scale({ stored: STORED, pick: { kind: "grid", key: 3 } })).toBeNull();
        expect(
            scale({ stored: STORED, pick: { kind: "typed", x: 9.84, y: 9.7 } }),
        ).toMatchObject({ x: 9.84, y: 9.7, source: "typed" });
    });
});
