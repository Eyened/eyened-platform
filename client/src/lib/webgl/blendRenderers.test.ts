import { Matrix } from "$lib/matrix";
import type { AbstractImage } from "./abstractImage";
import type { BlendLayerStyle } from "./blendRenderer";
import type { RenderTarget } from "./types";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const shader = vi.hoisted(() => ({
    constructed: 0,
    sources: [] as string[],
    pass: vi.fn(),
    dispose: vi.fn(),
}));

vi.mock("./FragmentShaderProgram", () => ({
    TextureShaderProgram: class {
        constructor(_webgl: unknown, source: string) {
            shader.constructed += 1;
            shader.sources.push(source);
        }
        pass = shader.pass;
        dispose = shader.dispose;
    },
}));

vi.mock("./imageRenderer", () => ({
    getBaseUniforms: () => ({ u_base: 1 }),
}));

const { BlendRenderer } = await import("./blendRenderer");

function image(id: string, colour = true): AbstractImage {
    return {
        image_id: id,
        texture: `${id}-tex`,
        width: 8,
        height: 4,
        webgl: {},
        supportsColorRenderModes: colour,
        selectTexture: (mode: string) => `${id}-${mode}`,
    } as unknown as AbstractImage;
}

function style(overrides: Partial<BlendLayerStyle> = {}): BlendLayerStyle {
    return {
        renderMode: "Original",
        windowLevel: { min: 0, max: 255 },
        tint: 0,
        colour: "#ffffff",
        opacity: 1,
        ...overrides,
    };
}

const target = {} as RenderTarget;
const viewer = {} as ViewerContext;

describe("BlendRenderer", () => {
    beforeEach(() => {
        shader.constructed = 0;
        shader.sources = [];
        shader.pass.mockClear();
        shader.dispose.mockClear();
    });

    it("compiles when baked mappings change and keeps the rest as uniforms", () => {
        const renderer = new BlendRenderer();
        const a = image("a");
        const b = image("b");
        renderer.setLayers([]);
        renderer.renderImage(viewer, target);
        expect(shader.pass).not.toHaveBeenCalled();

        renderer.setLayers([
            { image: a, mapping: "map-a", style: style(), weight: 1 },
            {
                image: b,
                mapping: "map-b",
                style: style({ opacity: 0.5, tint: 1, colour: "#ff0000" }),
                weight: 0.5,
            },
        ]);
        renderer.renderImage(viewer, target);
        expect(shader.constructed).toBe(1);
        expect(shader.pass).toHaveBeenCalledWith(
            target,
            expect.objectContaining({
                u_layer0: "a-Original",
                u_layer1: "b-Original",
                u_weight0: 1,
                u_weight1: 0.25,
                u_tint1: 1,
                u_colour1: [1, 0, 0],
                u_wl0: [0, 255],
                u_channel0: -2,
                u_size_anchor: [8, 4],
                u_composite: 0,
            }),
        );

        renderer.setLayers([
            { image: a, mapping: "map-a", style: style(), weight: 0 },
            { image: b, mapping: "map-b", style: style(), weight: 1 },
        ]);
        expect(shader.constructed).toBe(1);

        renderer.setLayers([
            { image: a, mapping: "map-a", style: style(), weight: 1 },
            { image: b, mapping: "map-c", style: style(), weight: 1 },
        ]);
        expect(shader.dispose).toHaveBeenCalledOnce();
        expect(shader.constructed).toBe(2);
        renderer.dispose();
    });

    it("sends a direct affine as a uniform and hides the layer without one", () => {
        const renderer = new BlendRenderer();
        const fixed = image("fixed");
        const moving = image("moving");
        const layers = (affine: Matrix | null) => [
            { image: fixed, mapping: "identity", style: style(), weight: 1 },
            { image: moving, mapping: { affine }, style: style(), weight: 1 },
        ];

        renderer.setLayers(layers(null));
        renderer.renderImage(viewer, target);
        expect(shader.sources[0]).toContain("uniform mat3 u_affine1;");
        expect(shader.pass).toHaveBeenLastCalledWith(
            target,
            expect.objectContaining({
                u_weight1: 0,
                u_affine1: Matrix.identity.asUniform,
                u_size1: [8, 4],
            }),
        );

        renderer.setLayers(layers(Matrix.identity));
        renderer.renderImage(viewer, target);
        expect(shader.constructed).toBe(1);
        expect(shader.pass).toHaveBeenLastCalledWith(
            target,
            expect.objectContaining({ u_weight1: 1 }),
        );
    });

    it("picks render-mode textures and channels per layer", () => {
        const renderer = new BlendRenderer();
        renderer.setLayers([
            {
                image: image("a"),
                mapping: "m",
                style: style({ renderMode: "CLAHE" }),
                weight: 1,
            },
            {
                image: image("b"),
                mapping: "m",
                style: style({ renderMode: "Green" }),
                weight: 1,
            },
            {
                image: image("c", false),
                mapping: "m",
                style: style({ renderMode: "Sharpened" }),
                weight: 1,
            },
        ]);
        renderer.setComposite("checkerboard", 32);
        renderer.renderImage(viewer, target);
        expect(shader.pass).toHaveBeenLastCalledWith(
            target,
            expect.objectContaining({
                u_layer0: "a-CLAHE",
                u_channel0: -2,
                u_layer1: "b-Green",
                u_channel1: 1,
                u_layer2: "c-Original",
                u_composite: 1,
                u_tile: 32,
            }),
        );
    });

    it("uses the plain texture for images without render-mode textures", () => {
        const renderer = new BlendRenderer();
        const plain = {
            ...image("p"),
            selectTexture: undefined,
        } as unknown as AbstractImage;
        renderer.setLayers([
            { image: plain, mapping: "m", style: style(), weight: 1 },
        ]);
        renderer.renderImage(viewer, target);
        expect(shader.pass).toHaveBeenLastCalledWith(
            target,
            expect.objectContaining({ u_layer0: "p-tex" }),
        );
    });
});
