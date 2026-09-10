import { describe, it, expect } from "vitest";
import { AffineRegistration, f, mat3 } from "./affine";
import { Matrix } from "$lib/matrix";
import { composeGlslPath } from "./composeGlslPath";
import { CompositeRegistration } from "./composite";

/** Parse the nine floats out of an emitted `mat3(...)` literal. */
function parseMat3(source: string): number[] {
    const args = source
        .replace(/^\s*mat3\(/, "")
        .replace(/\)\s*;?\s*$/, "")
        .split(",")
        .map((part) => Number(part.trim()));
    expect(args).toHaveLength(9);
    expect(args.every((v) => Number.isFinite(v))).toBe(true);
    return args;
}

/** Mimic GLSL `transform * vec3(x, y, 1)` for a column-major mat3 literal. */
function applyGlslMat3(
    args: number[],
    point: { x: number; y: number },
): { x: number; y: number } {
    const [c0x, c0y, c0z, c1x, c1y, c1z, c2x, c2y, c2z] = args;
    const x = c0x * point.x + c1x * point.y + c2x;
    const y = c0y * point.x + c1y * point.y + c2y;
    const w = c0z * point.x + c1z * point.y + c2z;
    return { x: x / w, y: y / w };
}

describe("affine GLSL helpers", () => {
    it("emits integer floats with .0", () => {
        expect(f(2)).toBe("2.0");
        expect(f(2.5)).toBe("2.5");
    });

    it("emits mat3 in column-major order matching Matrix.apply", () => {
        // Deliberately non-symmetric, with a non-trivial projective row.
        const M = new Matrix(2, 0.5, 10, -0.25, 3, -7, 0.001, 0.002, 1);
        const args = parseMat3(mat3(M));

        expect(args).toEqual(M.asUniform);

        for (const point of [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 0, y: 1 },
            { x: 13, y: -42 },
            { x: 256.5, y: 128.25 },
        ]) {
            const expected = M.apply(point);
            const actual = applyGlslMat3(args, point);
            expect(actual.x).toBeCloseTo(expected.x, 10);
            expect(actual.y).toBeCloseTo(expected.y, 10);
        }
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

    it("composes a composite registration without duplicate helpers", () => {
        const first = new AffineRegistration(
            "a",
            "b",
            new Matrix(1, 0, 10, 0, 1, 20, 0, 0, 1),
        );
        const second = new AffineRegistration(
            "b",
            "c",
            new Matrix(2, 0, 0, 0, 2, 0, 0, 0, 1),
        );
        const composite = new CompositeRegistration("a", "c", [first, second]);

        const composed = composeGlslPath([composite.glslMapping]);

        expect(composed.match(/vec2\s+map_0\s*\(/g)).toHaveLength(1);
        expect(composed.match(/vec2\s+map_1\s*\(/g)).toHaveLength(1);
        expect(composed.match(/vec2\s+mapping\s*\(/g)).toHaveLength(1);
    });
});
