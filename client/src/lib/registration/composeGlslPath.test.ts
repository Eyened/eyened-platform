import { describe, it, expect } from "vitest";
import { composeGlslPath } from "./composeGlslPath";

const hopA = `vec2 map_hop(vec2 uv) { return uv * 2.0; }`;
const hopB = `vec2 map_hop(vec2 uv) { return uv + 0.1; }`;

describe("composeGlslPath", () => {
    it("returns identity mapping for empty hops", () => {
        const src = composeGlslPath([]);
        expect(src).toContain("vec2 mapping(vec2 uv)");
        expect(src).toMatch(/return uv;/);
        expect(src).not.toContain("map_0");
    });

    it("renames a single hop to map_0 and chains it", () => {
        const src = composeGlslPath([hopA]);
        expect(src).toContain("vec2 map_0(vec2 uv)");
        expect(src).not.toContain("map_hop");
        expect(src).toContain("uv = map_0(uv);");
        expect(src).toContain("return uv;");
        // Body of map_0 must come from hopA (not a renamed empty stub).
        expect(src).toMatch(/vec2 map_0\(vec2 uv\)\s*\{\s*return uv \* 2\.0;/);
    });

    it("chains multiple hops in order", () => {
        const src = composeGlslPath([hopA, hopB]);
        expect(src).toContain("vec2 map_0(vec2 uv)");
        expect(src).toContain("vec2 map_1(vec2 uv)");
        const i0 = src.indexOf("uv = map_0(uv);");
        const i1 = src.indexOf("uv = map_1(uv);");
        expect(i0).toBeGreaterThan(-1);
        expect(i1).toBeGreaterThan(i0);
        // Pin hop bodies to indices: reverse([hopA, hopB]) would swap these.
        expect(src).toMatch(/vec2 map_0\(vec2 uv\)\s*\{\s*return uv \* 2\.0;/);
        expect(src).toMatch(/vec2 map_1\(vec2 uv\)\s*\{\s*return uv \+ 0\.1;/);
    });

    it("skips empty hop strings", () => {
        const src = composeGlslPath(["", hopA, "  "]);
        expect(src).toContain("map_0");
        expect(src).not.toContain("map_1");
    });

    it("throws if a non-empty hop lacks map_hop", () => {
        expect(() =>
            composeGlslPath([`vec2 mapping(vec2 uv) { return uv; }`]),
        ).toThrow(/map_hop/);
    });
});
