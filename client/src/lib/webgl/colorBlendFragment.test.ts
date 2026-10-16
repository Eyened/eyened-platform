import { describe, expect, it } from "vitest";
import { colorBlendFragment, colorBlendShaderKey } from "./colorBlendFragment";

const hop = `vec2 mapping(vec2 uv) { return uv; }`;

describe("colorBlendShaderKey", () => {
    it("includes overlay count and encodes null mappings", () => {
        expect(colorBlendShaderKey([])).toBe("0\n");
        expect(colorBlendShaderKey([null])).toBe("1\nnull");
        expect(colorBlendShaderKey([hop])).toBe(`1\n${hop}`);
        expect(colorBlendShaderKey([hop])).not.toBe(colorBlendShaderKey([null]));
    });

    it("produces the same key for identical mapping arrays", () => {
        const a = colorBlendShaderKey([hop, null]);
        const b = colorBlendShaderKey([hop, null]);
        expect(a).toBe(b);
        expect(a).toBe(`2\n${hop}\n---\nnull`);
    });
});

describe("colorBlendFragment", () => {
    it("samples the fixed layer at v_uv and the overlay through mapping_0", () => {
        const source = colorBlendFragment([hop]);
        expect(source).toContain("uniform sampler2D u_layer0");
        expect(source).toContain("uniform sampler2D u_layer1");
        expect(source).toContain("texture(u_layer0, v_uv)");
        expect(source).toContain("vec2 mapping_0(vec2 uv)");
        expect(source).toContain("texture(u_layer1, mapping_0(v_uv))");
        expect(source).not.toContain("vec2 mapping(vec2 uv)");
    });

    it("emits an untinted fixed layer when there are no overlays", () => {
        const source = colorBlendFragment([]);
        expect(source).toContain("u_untinted0");
        expect(source).not.toContain("u_layer1");
    });
});
