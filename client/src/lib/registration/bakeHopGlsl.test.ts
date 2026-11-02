import { describe, it, expect } from "vitest";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { ParabolicRegistration } from "./parabolic";
import { bakeHopGlsl, bakeParabolicHop, bakePixelSteps } from "./enfaceToProj";
import { Matrix } from "$lib/matrix";
import { composeGlslPath } from "./composeGlslPath";

/** Parse the two floats out of a `vec2(...)` literal (same spirit as parseMat3). */
function parseVec2(literal: string): [number, number] {
    const m = literal.match(/vec2\(\s*([^,]+)\s*,\s*([^)]+)\s*\)/);
    expect(m).not.toBeNull();
    const x = Number(m![1].trim());
    const y = Number(m![2].trim());
    expect(Number.isFinite(x)).toBe(true);
    expect(Number.isFinite(y)).toBe(true);
    return [x, y];
}

describe("bakeHopGlsl parabolic", () => {
    it("bakes coefficients and sizes into map_hop", () => {
        const glsl = bakeParabolicHop(
            [0.1, 0, 1, 0, 0, 0, 0],
            [0, 0.2, 0, 1, 0, 0, 0],
            [200, 100],
            [150, 80],
        );
        expect(glsl).toContain("vec2 map_hop(vec2 uv)");
        // Pin operand *positions*: src multiplies uv, dst divides the result.
        // A bare toContain("200.0") still passes if srcSize/dstSize are swapped.
        const srcLit = glsl!.match(/uv \* (vec2\([^)]+\))/);
        const dstLit = glsl!.match(/return p \/ (vec2\([^)]+\))/);
        expect(srcLit).not.toBeNull();
        expect(dstLit).not.toBeNull();
        expect(parseVec2(srcLit![1])).toEqual([200, 100]);
        expect(parseVec2(dstLit![1])).toEqual([150, 80]);
        expect(glsl).toContain("0.1");
        expect(glsl).toContain("0.2");
        expect(glsl).not.toContain("u_size_primary");
        expect(glsl).not.toContain("u_size_secondary");
    });

    it("dots each coefficient list on its own", () => {
        const glsl = bakeParabolicHop(
            [0.5, 0.25, 1, 0, 0.01],
            [0, 0, 0],
            [8, 8],
            [8, 8],
        );
        const dx = glsl!.match(/float dx_val = ([^;]+);/)?.[1];
        const dy = glsl!.match(/float dy_val = ([^;]+);/)?.[1];
        expect(dx).toContain("0.5 * 1.0");
        expect(dx).toContain("0.01 * x * x");
        expect(dy).toBe("0.0 * 1.0 + 0.0 * 1.0 + 0.0 * x");
        expect(dy).not.toContain("x * x");
    });

    it("bakes an empty side as zero", () => {
        const glsl = bakeParabolicHop([1], [], [8, 8], [8, 8]);
        expect(glsl).toContain("float dy_val = 0.0;");
        expect(glsl).toContain("1.0 * 1.0");
    });

    it("rejects an empty coefficient list", () => {
        expect(bakeParabolicHop([], [], [1, 1], [1, 1])).toBeNull();
    });

    it("bakes ParabolicRegistration via bakeHopGlsl", () => {
        const item = new ParabolicRegistration(
            "a",
            "b",
            [0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0],
        );
        const hop = bakeHopGlsl(item, [10, 10], [20, 20]);
        expect(hop).toContain("dx_val");
        const composed = composeGlslPath([hop!]);
        expect(composed).toContain("map_0");
    });

    it("folds an all-affine composite into one step", () => {
        const step = bakePixelSteps(
            new CompositeRegistration("a", "b", [
                new AffineRegistration("a", "mid", Matrix.identity),
                new AffineRegistration("mid", "b", Matrix.identity),
            ]),
        );
        expect(step).toHaveLength(1);
        expect(step![0]).toContain("mat3");
    });

    it("rejects a composite that contains a step with no pixel bake", () => {
        expect(
            bakePixelSteps(new CompositeRegistration("a", "b", [])),
        ).toBeNull();
        expect(
            bakePixelSteps(
                new CompositeRegistration("a", "b", [
                    { mapping: () => undefined } as never,
                ]),
            ),
        ).toBeNull();
        expect(
            bakePixelSteps({ mapping: () => undefined } as never),
        ).toBeNull();
    });

    it("bakes mixed affine+parabolic composites in pixel space", () => {
        const composite = new CompositeRegistration("a", "b", [
            new AffineRegistration("a", "mid", Matrix.identity),
            new ParabolicRegistration(
                "mid",
                "b",
                [0.5, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
            ),
        ]);
        const hop = bakeHopGlsl(composite, [100, 100], [50, 50]);
        expect(hop).not.toBeNull();
        expect(hop).toContain("mat3");
        expect(hop).toContain("dx_val");
        const srcLit = hop!.match(/uv \* (vec2\([^)]+\))/);
        const dstLit = hop!.match(/return p \/ (vec2\([^)]+\))/);
        expect(srcLit).not.toBeNull();
        expect(dstLit).not.toBeNull();
        expect(parseVec2(srcLit![1])).toEqual([100, 100]);
        expect(parseVec2(dstLit![1])).toEqual([50, 50]);
    });
});
