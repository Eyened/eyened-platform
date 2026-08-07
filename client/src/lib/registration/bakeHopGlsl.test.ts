import { describe, it, expect } from "vitest";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { ParabolicRegistration } from "./parabolic";
import { bakeHopGlsl, bakeParabolicHop } from "./enfaceToProj";
import { Matrix } from "$lib/matrix";
import { composeGlslPath } from "./composeGlslPath";

describe("bakeHopGlsl parabolic", () => {
    it("bakes coefficients and sizes into map_hop", () => {
        const glsl = bakeParabolicHop(
            [0.1, 0, 1, 0, 0, 0, 0],
            [0, 0.2, 0, 1, 0, 0, 0],
            [200, 100],
            [150, 80],
        );
        expect(glsl).toContain("vec2 map_hop(vec2 uv)");
        expect(glsl).toContain("200.0");
        expect(glsl).toContain("100.0");
        expect(glsl).toContain("150.0");
        expect(glsl).toContain("80.0");
        expect(glsl).toContain("0.1");
        expect(glsl).toContain("0.2");
        expect(glsl).not.toContain("u_size_primary");
        expect(glsl).not.toContain("u_size_secondary");
    });

    it("rejects malformed coefficient arrays", () => {
        expect(
            bakeParabolicHop([0, 0, 0], [0, 0, 0, 0, 0, 0, 0], [1, 1], [1, 1]),
        ).toBeNull();
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
        expect(hop).toContain("100.0");
        expect(hop).toContain("50.0");
    });
});
