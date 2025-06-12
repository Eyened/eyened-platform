import type { Color } from "$lib/utils";
import { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { colors } from "./colors";
import { ConnectedComponentsOverlay } from "./ConnectedComponentsOverlay";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import { SegmentationItem } from "$lib/webgl/segmentationItem";
import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { FilterList } from "$lib/datamodel/itemList";

export class SegmentationOverlay implements Overlay {

    private featureColors = new SvelteMap<Annotation, Color>();

    public readonly connectedComponentsOverlay: ConnectedComponentsOverlay;

    public readonly applyMasking = new SvelteSet<SegmentationItem>();
    public readonly renderOutline = $state(false);
    public readonly alpha = $state(0.8);
    public readonly segmentationContext: SegmentationContext;
    public readonly annotations: FilterList<Annotation>;

    constructor(
        private readonly viewerContext: ViewerContext,
        private readonly globalContext: GlobalContext

    ) {
        this.segmentationContext = new SegmentationContext();
        const image = viewerContext.image;
        this.annotations = image.segmentationAnnotations.filter(globalContext.annotationsFilter);

        this.connectedComponentsOverlay = new ConnectedComponentsOverlay(viewerContext, this.segmentationContext);
    }

    toggleMasking(segmentation: SegmentationItem) {
        if (this.applyMasking.has(segmentation)) {
            this.applyMasking.delete(segmentation);
        } else {
            this.applyMasking.add(segmentation);
        }
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
            segmentation.render(renderTarget, uniforms);
        }
    }

}