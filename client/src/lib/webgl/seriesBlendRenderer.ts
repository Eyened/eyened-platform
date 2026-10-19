import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "./abstractImage";
import { TextureShaderProgram } from "./FragmentShaderProgram";
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";
import { seriesBlendFragment } from "./seriesBlendFragment";
import type { RenderTarget } from "./types";

/**
 * Series blend. The program is compiled when the baked mappings change.
 * Weights are uniforms.
 */
export class SeriesBlendRenderer implements ImageRenderer {
    private shader: TextureShaderProgram | null = null;
    private shaderKey = "";
    private images: AbstractImage[] = [];
    private weights: number[] = [];

    setLayers(images: AbstractImage[], mappings: readonly string[]) {
        if (images.length === 0 || images.length !== mappings.length) return;
        this.images = images;
        const key = mappings.join("\0");
        if (key === this.shaderKey && this.shader) return;
        this.shader?.dispose();
        this.shader = new TextureShaderProgram(
            images[0]!.webgl,
            seriesBlendFragment(mappings),
        );
        this.shaderKey = key;
    }

    setWeights(weights: readonly number[]) {
        this.weights = [...weights];
    }

    dispose() {
        this.shader?.dispose();
        this.shader = null;
        this.shaderKey = "";
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const shader = this.shader;
        const images = this.images;
        if (!shader || images.length === 0) return;
        const uniforms = getBaseUniforms(viewerContext);
        images.forEach((image, layer) => {
            uniforms[`u_layer${layer}`] = image.texture;
            uniforms[`u_weight${layer}`] = this.weights[layer] ?? 0;
        });
        shader.pass(renderTarget, uniforms);
    }
}
