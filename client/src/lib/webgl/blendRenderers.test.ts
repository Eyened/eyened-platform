import { Matrix } from "$lib/matrix";
import type { AbstractImage } from "./abstractImage";
import type { RenderTarget } from "./types";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const shader = vi.hoisted(() => ({
    constructed: 0,
    pass: vi.fn(),
    dispose: vi.fn(),
}));

vi.mock("./FragmentShaderProgram", () => ({
    TextureShaderProgram: class {
        constructor() {
            shader.constructed += 1;
        }
        pass = shader.pass;
        dispose = shader.dispose;
    },
}));

vi.mock("./imageRenderer", () => ({
    getBaseUniforms: () => ({ u_base: 1 }),
}));

const { AffineBlendRenderer } = await import("./affineBlendRenderer");
const { SeriesBlendRenderer } = await import("./seriesBlendRenderer");

function image(id: string): AbstractImage {
    return {
        image_id: id,
        texture: `${id}-tex`,
        width: 8,
        height: 4,
        webgl: {},
    } as unknown as AbstractImage;
}

const target = {} as RenderTarget;
const viewer = {} as ViewerContext;

describe("AffineBlendRenderer", () => {
    beforeEach(() => {
        shader.constructed = 0;
        shader.pass.mockClear();
        shader.dispose.mockClear();
    });

    it("draws the fixed image alone until an overlay matrix exists", () => {
        const fixed = image("fixed");
        const moving = image("moving");
        const renderer = new AffineBlendRenderer(fixed.webgl);
        renderer.renderImage(viewer, target);
        expect(shader.pass).not.toHaveBeenCalled();

        renderer.setPair(fixed, null, null);
        renderer.setTint(1, [1, 0, 0], 0.5, 0, [0, 1, 1], 1);
        renderer.renderImage(viewer, target);
        expect(shader.pass).toHaveBeenCalledWith(
            target,
            expect.objectContaining({
                u_fixed: "fixed-tex",
                u_overlay: "fixed-tex",
                u_has_overlay: 0,
                u_fixed_opacity: 0.5,
                u_affine: Matrix.identity.asUniform,
            }),
        );

        renderer.setPair(fixed, moving, Matrix.identity);
        renderer.renderImage(viewer, target);
        expect(shader.pass).toHaveBeenLastCalledWith(
            target,
            expect.objectContaining({
                u_overlay: "moving-tex",
                u_has_overlay: 1,
            }),
        );
        renderer.dispose();
        expect(shader.dispose).toHaveBeenCalledOnce();
    });
});

describe("SeriesBlendRenderer", () => {
    beforeEach(() => {
        shader.constructed = 0;
        shader.pass.mockClear();
        shader.dispose.mockClear();
    });

    it("compiles when mappings change and keeps weights as uniforms", () => {
        const renderer = new SeriesBlendRenderer();
        const layers = [image("a"), image("b")];
        renderer.setLayers([], []);
        renderer.setLayers(layers, ["map-a"]);
        renderer.renderImage(viewer, target);
        expect(shader.pass).not.toHaveBeenCalled();

        renderer.setLayers(layers, ["map-a", "map-b"]);
        renderer.setWeights([1, 0.25]);
        renderer.renderImage(viewer, target);
        expect(shader.constructed).toBe(1);
        expect(shader.pass).toHaveBeenCalledWith(
            target,
            expect.objectContaining({
                u_layer0: "a-tex",
                u_layer1: "b-tex",
                u_weight0: 1,
                u_weight1: 0.25,
            }),
        );

        renderer.setLayers(layers, ["map-a", "map-b"]);
        expect(shader.constructed).toBe(1);

        renderer.setLayers(layers, ["map-a", "map-c"]);
        expect(shader.dispose).toHaveBeenCalledOnce();
        expect(shader.constructed).toBe(2);
        renderer.dispose();
    });
});
