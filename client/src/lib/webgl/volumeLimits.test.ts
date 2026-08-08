import { describe, expect, it } from "vitest";
import {
    fitsSliceStack,
    fitsTexture3D,
    type WebGLVolumeLimits,
} from "./volumeLimits";

const typicalLimits: WebGLVolumeLimits = {
    maxTexture3DSize: 2048,
    maxTexture2DSize: 16384,
};

describe("volumeLimits", () => {
    it("accepts standard OCT volumes for 3D textures", () => {
        expect(
            fitsTexture3D(
                { width: 512, height: 496, depth: 128 },
                typicalLimits,
            ),
        ).toBe(true);
    });

    it("rejects oversized slices for 3D textures", () => {
        expect(
            fitsTexture3D(
                { width: 4000, height: 4000, depth: 1 },
                typicalLimits,
            ),
        ).toBe(false);
    });

    it("accepts oversized slices for 2D stack storage", () => {
        expect(
            fitsSliceStack({ width: 4000, height: 4000 }, typicalLimits),
        ).toBe(true);
    });

    it("rejects slices that exceed 2D texture limits", () => {
        expect(
            fitsSliceStack({ width: 20000, height: 4000 }, typicalLimits),
        ).toBe(false);
    });
});

/** Regression: enface `_proj` world aspect from mm (pre-fix behavior). */
describe("enface proj aspect (mm world space)", () => {
    function aspectFromMm(
        width: number,
        height: number,
        width_mm: number,
        height_mm: number,
    ) {
        if (width_mm <= 0 || height_mm <= 0) return 1;
        return (height * width_mm) / (height_mm * width);
    }

    it("matches prior getAspectRatio for a typical OCT enface projection", () => {
        // width × B-scan count, lateral mm × between-B-scan mm
        const a = aspectFromMm(512, 128, 512 * 0.011, 128 * 0.03);
        expect(a).toBeCloseTo(0.011 / 0.03);
        expect(a).not.toBe(1);
    });
});
