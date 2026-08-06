import { describe, it, expect, vi } from "vitest";

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

import { applyInserts, compileShaderTemplate } from "./shaderTemplate";
import type { WebGL } from "./webgl";

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

describe("compileShaderTemplate", () => {
    it("applies inserts then constructs a TextureShaderProgram", () => {
        textureShaderProgram.mockClear();
        const webgl = {} as WebGL;
        compileShaderTemplate(webgl, "A\n/// @insert mapping\nB", {
            mapping: "vec2 mapping(vec2 uv) { return uv; }",
        });
        expect(textureShaderProgram).toHaveBeenCalledWith(
            webgl,
            "A\nvec2 mapping(vec2 uv) { return uv; }\nB",
        );
    });
});
