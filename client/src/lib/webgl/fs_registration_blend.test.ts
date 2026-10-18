import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const shader = readFileSync(
    resolve(import.meta.dirname, "./glsl/fs_registration_blend.frag"),
    "utf8",
);

describe("registration blend shader", () => {
    it("takes the affine matrix as a uniform", () => {
        expect(shader).toContain("uniform mat3 u_affine");
        expect(shader).not.toContain("mat3(");
    });

    it("mixes original colour with luminosity times a chosen colour", () => {
        expect(shader).toContain("uniform float u_fixed_mix");
        expect(shader).toContain("uniform vec3 u_overlay_colour");
        expect(shader).toContain("mix(rgb, luma * colour, amount)");
        expect(shader).toContain("u_fixed_opacity *");
        expect(shader).toContain("u_overlay_opacity *");
    });
});
