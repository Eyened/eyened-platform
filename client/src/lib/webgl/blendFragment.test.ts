import { describe, expect, it } from "vitest";
import { AFFINE_UNIFORM_LAYER, blendFragment } from "./blendFragment";

const identity = `vec2 mapping(vec2 uv) { return uv; }`;
const hop = `vec2 map_0(vec2 uv) { return uv; }
vec2 mapping(vec2 uv) {
  uv = map_0(uv);
  return uv;
}`;

describe("blendFragment", () => {
    it("keeps one sampler, weight, and style per image", () => {
        const source = blendFragment([identity, hop]);
        expect(source).toContain("const int LAYERS = 2;");
        for (const layer of [0, 1]) {
            expect(source).toContain(`uniform sampler2D u_layer${layer};`);
            expect(source).toContain(`uniform float u_weight${layer};`);
            expect(source).toContain(`uniform vec2 u_wl${layer};`);
            expect(source).toContain(`uniform int u_channel${layer};`);
            expect(source).toContain(`uniform float u_tint${layer};`);
            expect(source).toContain(`uniform vec3 u_colour${layer};`);
            expect(source).toContain(`vec2 mapping_${layer}(vec2 uv)`);
        }
    });

    it("renames hop helpers so two paths do not share map_0", () => {
        const source = blendFragment([hop, hop]);
        expect(source).toContain("vec2 map_l0_0(vec2 uv)");
        expect(source).toContain("vec2 map_l1_0(vec2 uv)");
        expect(source).toContain("uv = map_l0_0(uv);");
        expect(source).toContain("uv = map_l1_0(uv);");
        expect(source).not.toMatch(/[^_]map_0\(/);
    });

    it("reads an affine layer from uniforms instead of baked numbers", () => {
        const source = blendFragment([identity, AFFINE_UNIFORM_LAYER]);
        expect(source).toContain("uniform mat3 u_affine1;");
        expect(source).toContain("uniform vec2 u_size1;");
        expect(source).not.toContain("uniform mat3 u_affine0;");
        expect(source).not.toContain("mat3(");
    });

    it("drops samples that fall outside an image", () => {
        const source = blendFragment([identity]);
        expect(source).toContain("step(uv.x, 1.0)");
        expect(source).toContain("step(uv.y, 1.0)");
    });

    it("averages channels that layers share instead of adding them", () => {
        const source = blendFragment([identity, identity]);
        expect(source).toContain("rgb = total / max(vec3(1.0), covered);");
        expect(source).toContain("mix(vec3(1.0), u_colour0, u_tint0)");
    });

    it("picks one layer per checkerboard tile", () => {
        const source = blendFragment([identity, identity]);
        expect(source).toContain("uniform int u_composite;");
        expect(source).toContain("uniform float u_tile;");
        expect(source).toContain("mod(cell.x + cell.y, float(LAYERS))");
        expect(source).toContain("if (alphas[layer] <= 0.0) layer = 0;");
    });
});
