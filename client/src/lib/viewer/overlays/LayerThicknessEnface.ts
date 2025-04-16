import type { AbstractImage } from "$lib/webgl/abstractImage";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { LabelNumbersSegmentation } from "$lib/webgl/layerSegmentation";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

export class LayerThicknessEnfaceOverlay implements Overlay {

    constructor(readonly image: AbstractImage,
        readonly segmentation: LabelNumbersSegmentation,
        public layer: number,
        public scaling: number
    ) { }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const boundaries = this.segmentation.layerBoundaries;
        if (!boundaries) return;
        const uniforms = getBaseUniforms(viewerContext);
        uniforms.u_boundaries = boundaries.texture;
        uniforms.u_layer = this.layer - 1; // NOTE: thickness for background (0) is not calculated in boundaries
        uniforms.u_scaling = this.scaling;
        this.image.webgl.shaders.renderLayersEnface.pass(renderTarget, uniforms);
    }
}