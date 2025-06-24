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
import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { FilterList } from "$lib/datamodel/itemList";
import { BinarySegmentation } from "$lib/webgl/segmentation";

export class SegmentationOverlay implements Overlay {

    private featureColors = new SvelteMap<Annotation, Color>();

    public readonly applyConnectedComponents = new SvelteSet<SegmentationItem>();
    public readonly applyMasking = new SvelteSet<SegmentationItem>();
    public readonly renderOutline = $state(false);
    public readonly alpha = $state(1.0);
    public readonly segmentationContext = new SegmentationContext();
    public readonly annotations: FilterList<Annotation>;

    constructor(viewerContext: ViewerContext, globalContext: GlobalContext) {
        const image = viewerContext.image;
        this.annotations = image.segmentationAnnotations.filter(globalContext.annotationsFilter);
    }

    toggleMasking(segmentation: SegmentationItem) {
        toggleInSet(this.applyMasking, segmentation);
    }

    toggleConnectedComponents(segmentationItem: SegmentationItem) {
        toggleInSet(this.applyConnectedComponents, segmentationItem);
    }

    setFeatureColor(annotation: Annotation, color: Color) {
        this.featureColors.set(annotation, color);
    }

    private _colorIndex = 0;
    getFeatureColor(annotation: Annotation): Color {
        let color = this.featureColors.get(annotation);
        if (!color) {
            color = colors[(this._colorIndex++) % colors.length];
            this.setFeatureColor(annotation, color);
        }
        return color;
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const { image, index, hideOverlays } = viewerContext;
        if (hideOverlays) {
            return;
        }
        const {
            hideCreators,
            hideAnnotations
        } = this.segmentationContext;

        const baseUniforms = getBaseUniforms(viewerContext);
        const uniforms = {
            ...baseUniforms,
            u_alpha: this.alpha,
            u_smooth: true,
            u_outline: this.renderOutline
        };

        for (const annotation of this.annotations.$) {
            const segmentationItem = image.segmentationItems.get(annotation);
            if (!segmentationItem) continue;
            const segmentation = segmentationItem.getSegmentation(index);

            if (!segmentation) continue;
            if (hideAnnotations.has(annotation)) continue;
            if (hideCreators.has(annotation.creator)) continue;

            uniforms.u_color = this.getFeatureColor(annotation).map(c => c / 255);

            for (const ad of annotation.annotationData.$) {
                uniforms.u_threshold = ad.valueFloat ?? 0.5;
            }

            const applyMask = this.applyMasking.has(segmentationItem);
            uniforms.u_has_mask = false;
            uniforms.u_mask = null;
            uniforms.u_mask_bitmask = 0;
            if (applyMask) {
                const reference = annotation.annotationReference;
                if (reference) {
                    const referenceSegmentationItem = image.segmentationItems.get(reference);
                    if (!referenceSegmentationItem) continue;
                    const mask = referenceSegmentationItem.getSegmentation(index);
                    if (mask instanceof BinarySegmentation) {
                        uniforms.u_has_mask = true;
                        uniforms.u_mask = mask.binaryMask.texture;
                        uniforms.u_mask_bitmask = mask.binaryMask.bitmask;
                    }
                }
            }

            if (this.applyConnectedComponents.has(segmentationItem)) {
                (segmentation as BinarySegmentation).renderConnectedComponents(renderTarget, uniforms);
            } else {
                segmentation.render(renderTarget, uniforms);
            }
        }
    }
}