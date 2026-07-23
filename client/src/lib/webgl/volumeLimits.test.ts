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
            fitsTexture3D({ width: 512, height: 496, depth: 128 }, typicalLimits),
        ).toBe(true);
    });

    it("rejects oversized slices for 3D textures", () => {
        expect(
            fitsTexture3D({ width: 4000, height: 4000, depth: 1 }, typicalLimits),
        ).toBe(false);
    });

    it("accepts oversized slices for 2D stack storage", () => {
        expect(fitsSliceStack({ width: 4000, height: 4000 }, typicalLimits)).toBe(
            true,
        );
    });

    it("rejects slices that exceed 2D texture limits", () => {
        expect(
            fitsSliceStack({ width: 20000, height: 4000 }, typicalLimits),
        ).toBe(false);
    });
});
