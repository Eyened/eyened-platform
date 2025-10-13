import { toggleInSet, type Color } from "$lib/utils";
import { SegmentationContext, type Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import { BinaryMask } from "$lib/webgl/mask.svelte";
import { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { RenderTarget } from "$lib/webgl/types";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { ViewerWindowContext } from "../../viewer-window/viewerWindowContext.svelte";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { colors } from "./colors";

export class MainViewerContext implements Overlay {

    private featureColors = new SvelteMap<Segmentation, Color>();
    
    public readonly applyConnectedComponents = new SvelteSet<SegmentationItem>();
    public readonly applyMasking = new SvelteSet<SegmentationItem>();
    public active = $state(false);
    public renderOutline = $state(false);
    public alpha = $state(1.0);
    public highlightedFeatureIndex = $state<number | undefined>(undefined);
    public activeFeatureMask = $state<number | undefined>(undefined);
    public highlightedSegmentationItem: SegmentationItem | undefined = $state(undefined);
    public readonly segmentationContext: SegmentationContext
    

    constructor(
        public readonly instanceId: number,
        public readonly axis: number,
        public readonly viewerWindowContext: ViewerWindowContext,
        public readonly image: AbstractImage
    ) {
        this.segmentationContext = new SegmentationContext(instanceId, axis, viewerWindowContext, image);
    }

    toggleMasking(segmentation: SegmentationItem) {
        toggleInSet(this.applyMasking, segmentation);
    }

    toggleConnectedComponents(segmentationItem: SegmentationItem) {
        toggleInSet(this.applyConnectedComponents, segmentationItem);
    }

    setFeatureColor(segmentation: Segmentation, color: Color) {
        this.featureColors.set(segmentation, color);
    }

    private _colorIndex = 0;
    getFeatureColor(segmentation: Segmentation): Color {
        let color = this.featureColors.get(segmentation);
        if (!color) {
            color = colors[(this._colorIndex++) % colors.length];
            this.setFeatureColor(segmentation, color);
        }
        return color;
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        
        if (!this.active) {
            return;
        }
        const { image, index, hideOverlays } = viewerContext;
        if (hideOverlays) {
            return;
        }

        const baseUniforms = getBaseUniforms(viewerContext);
        const uniforms = {
            ...baseUniforms,
            u_threshold: 0.5,
            u_alpha: this.alpha,
            u_smooth: true,
            u_outline: this.renderOutline,
            activeIndices: this.segmentationContext.activeIndices
        };

        // Render grader segmentations
        for (const segmentation of this.segmentationContext.visibleGraderSegmentations) {
            const segmentationItem = this.segmentationContext.getSegmentationItem(segmentation);
            const mask = segmentationItem.getMask(index);
            if (!mask) continue;

            

            uniforms.u_color = this.getFeatureColor(segmentation).map(c => c / 255);
            uniforms.u_threshold = segmentationItem.threshold ?? segmentation.threshold;
            
            if (this.highlightedSegmentationItem == segmentationItem) {
                uniforms.u_highlighted_feature_index = this.highlightedFeatureIndex ?? 0;
                uniforms.u_active_feature_mask = this.activeFeatureMask ?? 0;
            } else {
                uniforms.u_highlighted_feature_index = 0;
                uniforms.u_active_feature_mask = 0; 
            }

            const applyMask = this.applyMasking.has(segmentationItem);
            uniforms.u_has_mask = false;
            uniforms.u_mask = null;
            uniforms.u_mask_bitmask = 0;
            if (applyMask && segmentation.reference_segmentation_id) {
                const referenceSegmentationItem = this.segmentationContext.getSegmentationItemById(segmentation.reference_segmentation_id);
                if (referenceSegmentationItem) {
                    const referenceMask = referenceSegmentationItem.getMask(index);
                    if (referenceMask instanceof BinaryMask) {
                        uniforms.u_has_mask = true;
                        uniforms.u_mask = referenceMask.bitMaskTexture.texture;
                        uniforms.u_mask_bitmask = referenceMask.bitMaskTexture.bitmask;
                    }
                }
            }

            if (this.applyConnectedComponents.has(segmentationItem)) {
                (mask as BinaryMask).renderConnectedComponents(renderTarget, uniforms);
            } else {
                mask.render(renderTarget, uniforms);
            }
        }
        
        // Render model segmentations
        for (const segmentation of this.segmentationContext.visibleModelSegmentations) {
            const segmentationItem = this.segmentationContext.getSegmentationItem(segmentation);
            const mask = segmentationItem.getMask(index);
            if (!mask) continue;

            uniforms.u_color = this.getFeatureColor(segmentation).map(c => c / 255);
            uniforms.u_threshold = segmentationItem.threshold ?? segmentation.threshold;
            
            if (this.highlightedSegmentationItem == segmentationItem) {
                uniforms.u_highlighted_feature_index = this.highlightedFeatureIndex ?? 0;
                uniforms.u_active_feature_mask = this.activeFeatureMask ?? 0;
            } else {
                uniforms.u_highlighted_feature_index = 0;
                uniforms.u_active_feature_mask = 0; 
            }

            uniforms.u_has_mask = false;
            uniforms.u_mask = null;
            uniforms.u_mask_bitmask = 0;

            if (this.applyConnectedComponents.has(segmentationItem)) {
                (mask as BinaryMask).renderConnectedComponents(renderTarget, uniforms);
            } else {
                mask.render(renderTarget, uniforms);
            }
        }
    }
}