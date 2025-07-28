import { toggleInSet, type Color } from "$lib/utils";
import { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { colors } from "./colors";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import { SegmentationItem } from "$lib/webgl/segmentationItem";
import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
import type { FilterList } from "$lib/datamodel/itemList";
import { BinaryMask } from "$lib/webgl/mask.svelte";
import type { Segmentation } from "$lib/datamodel/segmentation.svelte";

export class SegmentationOverlay implements Overlay {

    private featureColors = new SvelteMap<Segmentation, Color>();
    
    public readonly applyConnectedComponents = new SvelteSet<SegmentationItem>();
    public readonly applyMasking = new SvelteSet<SegmentationItem>();
    public active = $state(false);
    public renderOutline = $state(false);
    public alpha = $state(1.0);
    public highlightedFeatureIndex = $state<number | undefined>(undefined);
    public activeFeatureMask = $state<number | undefined>(undefined);
    public highlightedSegmentationItem: SegmentationItem | undefined = $state(undefined);
    public readonly segmentationContext = new SegmentationContext();
    public readonly allSegmentations: FilterList<Segmentation>;

    constructor(viewerContext: ViewerContext, globalContext: GlobalContext) {
        const instance = viewerContext.image.instance;
        this.allSegmentations = instance.segmentations
        .filter(globalContext.segmentationsFilter)
        .filter((s) => s.sparseAxis == viewerContext.axis);
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
        const {
            hideCreators
        } = this.segmentationContext;

        const baseUniforms = getBaseUniforms(viewerContext);
        const uniforms = {
            ...baseUniforms,
            u_threshold: 0.5,
            u_alpha: this.alpha,
            u_smooth: true,
            u_outline: this.renderOutline,
            activeIndices: this.segmentationContext.activeIndices
        };

        // for (const segmentation of this.segmentations.$) {
        for (const segmentation of this.segmentationContext.visibleSegmentations) {
            
            // console.log('segmentation', segmentation);

            const segmentationItem = image.segmentationItems.get(segmentation);
            if (!segmentationItem) continue;
            const mask = segmentationItem.getMask(index);

            if (!mask) continue;
            if (hideCreators.has(segmentation.creator)) continue;

            uniforms.u_color = this.getFeatureColor(segmentation).map(c => c / 255);
            uniforms.u_threshold = segmentation.threshold;
            
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
            if (applyMask) {
                const reference = segmentation.reference;
                if (reference) {
                    const referenceSegmentationItem = image.segmentationItems.get(reference);
                    if (!referenceSegmentationItem) continue;
                    const mask = referenceSegmentationItem.getMask(index);
                    if (mask instanceof BinaryMask) {
                        uniforms.u_has_mask = true;
                        uniforms.u_mask = mask.bitMaskTexture.texture;
                        uniforms.u_mask_bitmask = mask.bitMaskTexture.bitmask;
                    }
                }
            }


            if (this.applyConnectedComponents.has(segmentationItem)) {
                (mask as BinaryMask).renderConnectedComponents(renderTarget, uniforms);
            } else {
                mask.render(renderTarget, uniforms);
            }
        }
    }
}