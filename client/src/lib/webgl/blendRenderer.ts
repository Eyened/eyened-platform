import { Matrix } from "$lib/matrix";
import {
    isRenderModeAvailable,
    type RenderMode,
    type WindowLevel,
} from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "./abstractImage";
import {
    AFFINE_UNIFORM_LAYER,
    blendFragment,
    COMPOSITE_CHECKERBOARD,
    COMPOSITE_OVERLAY,
} from "./blendFragment";
import { TextureShaderProgram } from "./FragmentShaderProgram";
import type { Image2D } from "./image2D";
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";
import { parseHexColour } from "./parseHexColour";
import type { RenderTarget } from "./types";

export type BlendComposite = "overlay" | "checkerboard";

/** Per-layer look. `tint` is 0 for the original colours and 1 for luminosity times `colour`. */
export type BlendLayerStyle = {
    renderMode: RenderMode;
    windowLevel: WindowLevel;
    tint: number;
    colour: string;
    opacity: number;
};

/** A baked GLSL path, or a direct affine that is sent as a uniform. */
export type BlendMapping = string | { affine: Matrix | null };

export type BlendLayer = {
    image: AbstractImage;
    mapping: BlendMapping;
    style: BlendLayerStyle;
    /** Series weight. Multiplies the style opacity. */
    weight: number;
};

const CHANNELS: Partial<Record<RenderMode, number>> = {
    Luminance: -1,
    Red: 0,
    Green: 1,
    Blue: 2,
};

/**
 * Blends registered layers in one shader. The program is compiled when the
 * baked mappings change. Styles, weights, affine uniforms, and the composite
 * mode are uniforms.
 */
export class BlendRenderer implements ImageRenderer {
    private shader: TextureShaderProgram | null = null;
    private shaderKey = "";
    private layers: BlendLayer[] = [];
    private composite: BlendComposite = "overlay";
    private tile = 64;

    setLayers(layers: BlendLayer[]) {
        if (layers.length === 0) return;
        const mappings = layers.map(({ mapping }) =>
            typeof mapping === "string" ? mapping : AFFINE_UNIFORM_LAYER,
        );
        const key = mappings.join("\0");
        if (key !== this.shaderKey || !this.shader) {
            const shader = new TextureShaderProgram(
                layers[0]!.image.webgl,
                blendFragment(mappings),
            );
            this.shader?.dispose();
            this.shader = shader;
            this.shaderKey = key;
        }
        this.layers = layers;
    }

    /** `tile` is the checkerboard square size in first-image pixels. */
    setComposite(composite: BlendComposite, tile: number) {
        this.composite = composite;
        this.tile = tile;
    }

    dispose() {
        this.shader?.dispose();
        this.shader = null;
        this.shaderKey = "";
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const shader = this.shader;
        const layers = this.layers;
        if (!shader || layers.length === 0) return;
        const anchor = layers[0]!.image;
        const uniforms = getBaseUniforms(viewerContext);
        uniforms.u_size_anchor = [anchor.width, anchor.height];
        uniforms.u_composite =
            this.composite === "checkerboard"
                ? COMPOSITE_CHECKERBOARD
                : COMPOSITE_OVERLAY;
        uniforms.u_tile = this.tile;
        layers.forEach(({ image, mapping, style, weight }, layer) => {
            const renderMode = isRenderModeAvailable(
                image.supportsColorRenderModes,
                style.renderMode,
            )
                ? style.renderMode
                : "Original";
            let present = 1;
            if (typeof mapping !== "string") {
                present = mapping.affine ? 1 : 0;
                uniforms[`u_affine${layer}`] = (
                    mapping.affine ?? Matrix.identity
                ).asUniform;
                uniforms[`u_size${layer}`] = [image.width, image.height];
            }
            uniforms[`u_layer${layer}`] = layerTexture(image, renderMode);
            uniforms[`u_weight${layer}`] = present * weight * style.opacity;
            uniforms[`u_wl${layer}`] = [
                style.windowLevel.min,
                style.windowLevel.max,
            ];
            uniforms[`u_channel${layer}`] = CHANNELS[renderMode] ?? -2;
            uniforms[`u_tint${layer}`] = style.tint;
            uniforms[`u_colour${layer}`] = [...parseHexColour(style.colour)];
        });
        shader.pass(renderTarget, uniforms);
    }
}

function layerTexture(image: AbstractImage, renderMode: RenderMode) {
    const selectTexture = (image as Partial<Image2D>).selectTexture;
    return selectTexture
        ? selectTexture.call(image as Image2D, renderMode)
        : image.texture;
}
