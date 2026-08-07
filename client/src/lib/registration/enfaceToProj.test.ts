import { describe, it, expect } from "vitest";
import {
    bakeEnfaceToProjHop,
    resolveRasterMaxMatchDistPx,
} from "./enfaceToProj";
import { LinePhotoLocator } from "./photoLocators";
import { medianRasterLineSpacingPx } from "./photoLocatorHitSpec";

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

describe("medianRasterLineSpacingPx", () => {
    it("returns median consecutive gap for parallel lines", () => {
        // gaps 10, 10, 20 → median 10
        const lines = [horiz(0, 0), horiz(10, 1), horiz(20, 2), horiz(40, 3)];
        expect(medianRasterLineSpacingPx(lines)).toBeCloseTo(10);
    });
});

describe("resolveRasterMaxMatchDistPx", () => {
    it("prefers DICOM slice thickness converted via enface mm/px", () => {
        const lines = [horiz(0, 0), horiz(10, 1)];
        // 0.12 mm / 0.012 mm/px = 10 px
        expect(resolveRasterMaxMatchDistPx(lines, 0.12, 0.012)).toBeCloseTo(10);
    });

    it("falls back to median line spacing when thickness missing", () => {
        const lines = [horiz(0, 0), horiz(10, 1), horiz(20, 2)];
        expect(resolveRasterMaxMatchDistPx(lines, null, null)).toBeCloseTo(10);
    });
});

describe("bakeEnfaceToProjHop raster gate", () => {
    it("keeps nearest-neighbor but rejects beyond maxMatchDistPx", () => {
        const glsl = bakeEnfaceToProjHop(
            [horiz(40, 0), horiz(50, 1)],
            [200, 200],
            [100, 50],
            10,
        );
        expect(glsl).toBeTruthy();
        expect(glsl!).toContain("bestDist");
        expect(glsl!).toContain("if (bestDist > 10.0)");
        expect(glsl!).toContain("return vec2(-1.0)");
    });

    it("omits gate when maxMatchDistPx is null", () => {
        const glsl = bakeEnfaceToProjHop(
            [horiz(40, 0), horiz(50, 1)],
            [200, 200],
            [100, 50],
            null,
        );
        expect(glsl).toBeTruthy();
        expect(glsl!).not.toContain("return vec2(-1.0)");
    });
});
