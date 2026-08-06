import { describe, it, expect } from "vitest";
import { applyInserts, shaderCacheKey } from "./shaderTemplate";

describe("applyInserts", () => {
    it("replaces insert slots", () => {
        const template = `A\n// @insert mapping\nB`;
        const out = applyInserts(template, {
            mapping: "vec2 mapping(vec2 uv) { return uv; }",
        });
        expect(out).toContain("vec2 mapping(vec2 uv)");
        expect(out).not.toContain("@insert");
    });

    it("throws if a slot is missing from the template", () => {
        expect(() =>
            applyInserts("no slots", { mapping: "x" }),
        ).toThrow(/mapping/);
    });
});

describe("shaderCacheKey", () => {
    it("is stable for same inputs", () => {
        const a = shaderCacheKey("t", { mapping: "m1" });
        const b = shaderCacheKey("t", { mapping: "m1" });
        expect(a).toBe(b);
    });

    it("changes when insert content changes", () => {
        const a = shaderCacheKey("t", { mapping: "m1" });
        const b = shaderCacheKey("t", { mapping: "m2" });
        expect(a).not.toBe(b);
    });
});
