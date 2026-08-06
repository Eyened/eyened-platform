import { beforeEach, describe, it, expect, vi } from "vitest";

const { textureShaderProgram } = vi.hoisted(() => ({
    textureShaderProgram: vi.fn(),
}));

vi.mock("./FragmentShaderProgram", () => ({
    TextureShaderProgram: class {
        constructor(webgl: unknown, source: string) {
            textureShaderProgram(webgl, source);
        }
    },
}));

import {
    applyInserts,
    getShaderTemplateCache,
    shaderCacheKey,
    ShaderTemplateCache,
} from "./shaderTemplate";
import type { WebGL } from "./webgl";

const webgl = {} as WebGL;
const template = "// @insert mapping";

describe("applyInserts", () => {
    it("replaces insert slots", () => {
        const template = `A\n// @insert mapping\nB`;
        const out = applyInserts(template, {
            mapping: "vec2 mapping(vec2 uv) { return uv; }",
        });
        expect(out).toContain("vec2 mapping(vec2 uv)");
        expect(out).not.toContain("@insert");
    });

    it("prefers /// @insert so vite-plugin-glsl-preserved markers work", () => {
        // vite-plugin-glsl strips `//` comments but keeps `///`.
        const template = `A\n/// @insert mapping\nB`;
        const out = applyInserts(template, {
            mapping: "vec2 mapping(vec2 uv) { return uv; }",
        });
        expect(out).toBe("A\nvec2 mapping(vec2 uv) { return uv; }\nB");
        expect(out).not.toMatch(/^\//m);
    });

    it("throws if a slot is missing from the template", () => {
        expect(() => applyInserts("no slots", { mapping: "x" })).toThrow(
            /mapping/,
        );
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

describe("ShaderTemplateCache", () => {
    beforeEach(() => {
        textureShaderProgram.mockReset();
    });

    it("compiles once per key and returns the cached program", () => {
        const cache = new ShaderTemplateCache();
        const first = cache.getOrCompile(webgl, template, { mapping: "m" });
        const second = cache.getOrCompile(webgl, template, { mapping: "m" });

        expect(first).toBe(second);
        expect(textureShaderProgram).toHaveBeenCalledOnce();
    });

    it("throws once on failure, then returns null without recompiling", () => {
        textureShaderProgram.mockImplementation(() => {
            throw new Error("compile failed");
        });
        vi.spyOn(console, "error").mockImplementation(() => {});
        const cache = new ShaderTemplateCache();

        expect(() =>
            cache.getOrCompile(webgl, template, { mapping: "bad" }),
        ).toThrow(/compile failed/);
        expect(
            cache.getOrCompile(webgl, template, { mapping: "bad" }),
        ).toBeNull();
        expect(textureShaderProgram).toHaveBeenCalledOnce();
    });
});

describe("getShaderTemplateCache", () => {
    it("returns one cache per webgl context", () => {
        const a = {} as WebGL;
        const b = {} as WebGL;

        expect(getShaderTemplateCache(a)).toBe(getShaderTemplateCache(a));
        expect(getShaderTemplateCache(a)).not.toBe(getShaderTemplateCache(b));
    });
});
