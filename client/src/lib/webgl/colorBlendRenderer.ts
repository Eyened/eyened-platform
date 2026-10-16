import { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";
import { colorBlendFragment, colorBlendShaderKey } from "./colorBlendFragment";

const NULL_OVERLAY_MAPPING = `vec2 mapping(vec2 uv) { return uv; }`;

export type ColorBlendLayer = {
    texture: WebGLTexture;
    width: number;
    height: number;
    colour: readonly [number, number, number];
    untinted: boolean;
    mapping: string | null;
};

export class ColorBlendRenderer implements ImageRenderer {
    private shader: TextureShaderProgram | null = null;
    private shaderKey = "";
    private layers: ColorBlendLayer[] = [];

    constructor(private readonly webgl: WebGL) {}

    setLayers(layers: ColorBlendLayer[]) {
        this.layers = layers;
        const overlayMappings = layers.slice(1).map((layer) => layer.mapping);
        const key = colorBlendShaderKey(overlayMappings);
        if (key === this.shaderKey && this.shader) return;
        this.shaderKey = key;
        const mappings = overlayMappings.map((mapping) => mapping ?? NULL_OVERLAY_MAPPING);
        this.shader = new TextureShaderProgram(this.webgl, colorBlendFragment(mappings));
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        if (!this.shader || this.layers.length === 0) return;
        const uniforms = getBaseUniforms(viewerContext);
        this.layers.forEach((layer, index) => {
            uniforms[`u_layer${index}`] = layer.texture;
            uniforms[`u_colour${index}`] = [...layer.colour];
            uniforms[`u_untinted${index}`] = layer.untinted ? 1 : 0;
        });
        this.shader.pass(renderTarget, uniforms);
    }
}
