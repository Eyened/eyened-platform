import { describe, expect, it } from "vitest";
import { seriesBlendFragment } from "./seriesBlendFragment";

const identity = `vec2 mapping(vec2 uv) { return uv; }`;
const hop = `vec2 map_0(vec2 uv) { return uv; }
vec2 mapping(vec2 uv) {
  uv = map_0(uv);
  return uv;
}`;

describe("seriesBlendFragment", () => {
    it("keeps one sampler and one weight uniform per image", () => {
        const source = seriesBlendFragment([identity, hop]);
        expect(source).toContain("uniform sampler2D u_layer0;");
        expect(source).toContain("uniform sampler2D u_layer1;");
        expect(source).toContain("uniform float u_weight0;");
        expect(source).toContain("uniform float u_weight1;");
        expect(source).toContain("vec2 mapping_0(vec2 uv)");
        expect(source).toContain("vec2 mapping_1(vec2 uv)");
    });

    it("renames hop helpers so two paths do not share map_0", () => {
        const source = seriesBlendFragment([hop, hop]);
        expect(source).toContain("vec2 map_l0_0(vec2 uv)");
        expect(source).toContain("vec2 map_l1_0(vec2 uv)");
        expect(source).toContain("uv = map_l0_0(uv);");
        expect(source).toContain("uv = map_l1_0(uv);");
        expect(source).not.toMatch(/[^_]map_0\(/);
    });

    it("drops samples that fall outside an image", () => {
        const source = seriesBlendFragment([identity]);
        expect(source).toContain("step(uv.x, 1.0)");
        expect(source).toContain("step(uv.y, 1.0)");
    });
});
