import { describe, it, expect } from "vitest";
import {
    bakeEnfaceToProjHop,
    resolveCircularMaxMatchDistPx,
    resolveRasterMaxMatchDistPx,
} from "./enfaceToProj";
import { CirclePhotoLocator, LinePhotoLocator } from "./photoLocators";
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
    it("prefers half DICOM slice thickness in enface px", () => {
        const lines = [horiz(0, 0), horiz(10, 1)];
        // 0.12 mm / 0.012 mm/px = 10 px full → half-gap 5
        expect(resolveRasterMaxMatchDistPx(lines, 0.12, 0.012)).toBeCloseTo(5);
    });

    it("falls back to half median line spacing when thickness missing", () => {
        const lines = [horiz(0, 0), horiz(10, 1), horiz(20, 2)];
        expect(resolveRasterMaxMatchDistPx(lines, null, null)).toBeCloseTo(5);
    });

    it("uses 1px strip for a singleton line", () => {
        expect(resolveRasterMaxMatchDistPx([horiz(40, 0)], null, null)).toBe(1);
    });
});

describe("resolveCircularMaxMatchDistPx", () => {
    it("uses a thin annulus for a singleton circle", () => {
        const ring = new CirclePhotoLocator(
            "ir",
            "oct",
            { x: 50, y: 50 },
            200,
            Math.PI,
            0,
            100,
        );
        expect(resolveCircularMaxMatchDistPx([ring], null, null)).toBeCloseTo(
            10,
        );
    });

    it("uses half median radius gap for concentric rings", () => {
        const rings = [
            new CirclePhotoLocator("ir", "oct", { x: 50, y: 50 }, 20, 0, 0, 100),
            new CirclePhotoLocator("ir", "oct", { x: 50, y: 50 }, 30, 0, 1, 100),
        ];
        expect(resolveCircularMaxMatchDistPx(rings, null, null)).toBeCloseTo(5);
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

describe("bakeEnfaceToProjHop circular angle wrap", () => {
    it("fract-wraps start_angle so circumferential UV stays in [0,1)", () => {
        const ring = new CirclePhotoLocator(
            "ir",
            "oct",
            { x: 50, y: 50 },
            20,
            Math.PI,
            0,
            100,
        );
        const glsl = bakeEnfaceToProjHop([ring], [200, 200], [100, 50], null);
        expect(glsl).toBeTruthy();
        expect(glsl!).toContain("fract(angle / TWO_PI)");
        expect(glsl!).not.toContain(
            "float r = angle / (2.0 * 3.141592653589793)",
        );
    });
});
