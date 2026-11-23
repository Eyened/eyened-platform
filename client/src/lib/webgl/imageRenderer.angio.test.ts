import { describe, expect, it } from "vitest";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { getBaseUniforms } from "./imageRenderer";

function context(hasFlow: boolean): ViewerContext {
    const texture = { name: "structural" };
    return {
        index: 3,
        renderMode: "Original",
        angioDisplayMode: "overlay",
        windowLevel: { min: 0, max: 255 },
        webglTransform: { asUniform: [1] },
        image: {
            hasFlow,
            texture,
            flowTexture: hasFlow ? { name: "flow" } : null,
            width: 4,
            height: 5,
            depth: 6,
            supportsColorRenderModes: false,
        },
    } as unknown as ViewerContext;
}

describe("getBaseUniforms", () => {
    it("binds the structural texture when the image has no flow", () => {
        const uniforms = getBaseUniforms(context(false));
        expect(uniforms.u_angio_mode).toBe(0);
        expect(uniforms.u_flow).toEqual({ name: "structural" });
    });

    it("binds the flow texture in overlay mode", () => {
        const uniforms = getBaseUniforms(context(true));
        expect(uniforms.u_angio_mode).toBe(2);
        expect(uniforms.u_flow).toEqual({ name: "flow" });
    });
});
