import type { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { BinarySegmentation } from "$lib/webgl/binarySegmentation.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerContext } from "../viewerContext.svelte";
import { colorsFlat } from "./colors";
import { SvelteSet } from "svelte/reactivity";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

export class ConnectedComponentsOverlay {

    private readonly renderConnectedComponents: TextureShaderProgram;
    public readonly mode = new SvelteSet<BinarySegmentation>();

    constructor(
        public readonly viewerContext: ViewerContext,
        public readonly segmentationContext: SegmentationContext
    ) {
        const shaders = viewerContext.shaders;
        this.renderConnectedComponents = shaders.renderConnectedComponents;
    }

    toggleMode(segmentation: BinarySegmentation) {
        if (this.mode.has(segmentation)) {
            this.mode.delete(segmentation);
        } else {
            this.mode.add(segmentation);
        }
    }


    paint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const { index } = viewerContext;
        const {
            hideCreators,
            hideFeatures,
            hideSegmentations,
            hideAnnotations
        } = this.segmentationContext;

        const baseUniforms = getBaseUniforms(viewerContext);
        const uniforms = {
            ...baseUniforms,
            u_alpha: 1.0
        };

        for (const segmentation of this.mode) {
            const { annotation } = segmentation;
            if (hideAnnotations.has(annotation)) continue;
            if (hideSegmentations.has(segmentation)) continue;
            if (hideCreators.has(annotation.creator)) continue;
            if (hideFeatures.has(annotation.feature)) continue;

            uniforms.u_annotation = segmentation.getConnectedComponents(index);
            uniforms.u_colors = colorsFlat;

            this.renderConnectedComponents.pass(renderTarget, uniforms);
        }

    }

}
