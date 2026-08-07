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
