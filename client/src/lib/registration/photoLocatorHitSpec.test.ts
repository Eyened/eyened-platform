import { describe, it, expect } from "vitest";
import { LinePhotoLocator } from "./photoLocators";
import { buildPhotoLocatorHitSpec } from "./photoLocatorHitSpec";

function horiz(y: number, index: number) {
    return new LinePhotoLocator(
        "ir",
        "oct",
        { x: 0, y },
        { x: 100, y },
        index,
        100,
    );
}

describe("buildPhotoLocatorHitSpec raster", () => {
    it("classifies parallel horizontals as raster", () => {
        const spec = buildPhotoLocatorHitSpec([horiz(40, 0), horiz(50, 1)]);
        expect(spec.kind).toBe("raster");
    });

    it("hits midway with half-gap delta (5px for 10px spacing)", () => {
        const spec = buildPhotoLocatorHitSpec([horiz(40, 0), horiz(50, 1)]);
        const mid = spec.query({ x: 50, y: 42 });
        expect(mid).toBeDefined();
        expect(mid!.index).toBe(0);
        expect(mid!.delta).toBeCloseTo(5);
        expect(mid!.y).toBeCloseTo(0.5);
    });

    it("misses beyond the exterior half-gap past first/last", () => {
        const spec = buildPhotoLocatorHitSpec([horiz(40, 0), horiz(50, 1)]);
        expect(spec.query({ x: 50, y: 34 })).toBeUndefined(); // 6px above first
        expect(spec.query({ x: 50, y: 56 })).toBeUndefined(); // 6px below last
    });

    it("misses past segment ends", () => {
        const spec = buildPhotoLocatorHitSpec([horiz(40, 0), horiz(50, 1)]);
        expect(spec.query({ x: -10, y: 40 })).toBeUndefined();
        expect(spec.query({ x: 110, y: 40 })).toBeUndefined();
    });

    it("singleton uses delta=1", () => {
        const spec = buildPhotoLocatorHitSpec([horiz(40, 0)]);
        expect(spec.query({ x: 50, y: 40.5 })?.index).toBe(0);
        expect(spec.query({ x: 50, y: 42 })).toBeUndefined();
    });
});

function ray(
    angle: number,
    index: number,
    hub = { x: 50, y: 50 },
    len = 40,
) {
    return new LinePhotoLocator(
        "ir",
        "oct",
        hub,
        {
            x: hub.x + len * Math.cos(angle),
            y: hub.y + len * Math.sin(angle),
        },
        index,
        100,
    );
}

describe("buildPhotoLocatorHitSpec radial", () => {
    it("classifies a concurrent fan as radial", () => {
        const spec = buildPhotoLocatorHitSpec([
            ray(0, 0),
            ray(Math.PI / 6, 1),
            ray(Math.PI / 3, 2),
        ]);
        expect(spec.kind).toBe("radial");
    });

    it("misses outside the exterior half angular gap", () => {
        const a0 = 0;
        const a1 = Math.PI / 5;
        const spec = buildPhotoLocatorHitSpec([ray(a0, 0), ray(a1, 1)]);
        const hub = { x: 50, y: 50 };
        const outside = {
            x: hub.x + 30 * Math.cos(-a1),
            y: hub.y + 30 * Math.sin(-a1),
        };
        expect(spec.query(outside)).toBeUndefined();
    });

    it("hits between rays within half angular gap", () => {
        const a0 = 0;
        const a1 = Math.PI / 5;
        const spec = buildPhotoLocatorHitSpec([ray(a0, 0), ray(a1, 1)]);
        const hub = { x: 50, y: 50 };
        const midAng = a0 + (a1 - a0) * 0.25;
        const p = {
            x: hub.x + 30 * Math.cos(midAng),
            y: hub.y + 30 * Math.sin(midAng),
        };
        const hit = spec.query(p);
        expect(hit).toBeDefined();
        expect(hit!.index).toBe(0);
    });
});
