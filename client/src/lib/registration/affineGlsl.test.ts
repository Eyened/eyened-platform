import { describe, it, expect } from "vitest";
import { AffineRegistration, f, mat3 } from "./affine";
import { Matrix } from "$lib/matrix";
import { composeGlslPath } from "./composeGlslPath";

describe("affine GLSL helpers", () => {
    it("emits integer floats with .0", () => {
        expect(f(2)).toBe("2.0");
        expect(f(2.5)).toBe("2.5");
    });

    it("glslMapping uses map_hop and composes", () => {
        const M = new Matrix(1, 0, 10, 0, 1, 20, 0, 0, 1);
        const item = new AffineRegistration("a", "b", M);
        expect(item.glslMapping).toContain("vec2 map_hop(vec2 uv)");
        expect(item.glslMapping).not.toMatch(/vec2 mapping\s*\(/);
        const composed = composeGlslPath([item.glslMapping]);
        expect(composed).toContain("map_0");
        expect(composed).toContain("u_size_primary");
        expect(composed).toContain("u_size_secondary");
        expect(composed).toContain(mat3(M).trim().split("\n")[0]);
    });
});
