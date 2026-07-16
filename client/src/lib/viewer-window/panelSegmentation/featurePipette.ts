import type { Position2D } from "$lib/types";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { Mask } from "$lib/webgl/mask.svelte";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import {
    segToImageMatrix,
    segmentationPlaneSize,
} from "$lib/webgl/segmentationProjection";
import type { DrawingArray } from "$lib/webgl/mask.svelte";
import {
    getSegmentationKey,
    type Segmentation,
    type SegmentationContext,
} from "./segmentationContext.svelte";
import { orderSegmentationsByCreator } from "./segmentationUtils";

/** Pipette hotkey: A (feature pick). E remains contrast-enhanced render mode. */
export const FEATURE_PIPETTE_KEY = "KeyA";

type MultiFeatureRep = "MultiClass" | "MultiLabel";
type IndependentMaskRep = "Binary" | "DualBitMask" | "Probability";

function isTypingTarget(event: KeyboardEvent): boolean {
    if (!(event.target instanceof HTMLElement)) return false;
    const tag = event.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;
    return event.target.isContentEditable;
}

/** Visible segmentations in panel list order (model block, then user, then others). */
export function getVisibleSegmentationsInPanelOrder(
    segmentationContext: SegmentationContext,
    userId: number,
): Segmentation[] {
    const models = segmentationContext.modelVisible
        ? segmentationContext.modelSegmentations
        : [];
    const ordered = orderSegmentationsByCreator(
        models,
        segmentationContext.graderSegmentations,
        userId,
    );
    return ordered.filter((s) =>
        segmentationContext.shownSegmentations.has(getSegmentationKey(s)),
    );
}

/**
 * Topmost-first for hit testing (matches MainViewer paint order: graders, then models).
 */
export function getVisibleSegmentationsTopmostFirst(
    segmentationContext: SegmentationContext,
    userId: number,
): Segmentation[] {
    const visible = getVisibleSegmentationsInPanelOrder(
        segmentationContext,
        userId,
    );
    const models = visible.filter(
        (s) => s.annotation_type === "model_segmentation",
    );
    const graders = visible.filter(
        (s) => s.annotation_type === "grader_segmentation",
    );
    const topmost: Segmentation[] = [];
    for (let i = models.length - 1; i >= 0; i--) {
        topmost.push(models[i]!);
    }
    for (let i = graders.length - 1; i >= 0; i--) {
        topmost.push(graders[i]!);
    }
    return topmost;
}

function segmentationPixelIndex(
    segmentation: Segmentation,
    image: AbstractImage,
    imagePosition: Position2D,
): { x: number; y: number; idx: number } | null {
    const plane = segmentationPlaneSize(segmentation, image);
    const segPos = segToImageMatrix(segmentation).inverse.apply(imagePosition);
    const x = Math.floor(segPos.x);
    const y = Math.floor(segPos.y);
    if (x < 0 || y < 0 || x >= plane.width || y >= plane.height) {
        return null;
    }
    return { x, y, idx: y * plane.width + x };
}

function readAnnotationAtPixel(
    mask: Mask,
    segmentation: Segmentation,
    segmentationItem: SegmentationItem,
    pixelIdx: number,
): number {
    const rep = segmentation.data_representation;
    if (!("exportData" in mask)) {
        return 0;
    }
    const data = (mask as { exportData(): DrawingArray }).exportData();

    if (rep === "Probability") {
        const v = Number((data as Float32Array)[pixelIdx] ?? 0);
        const th = segmentationItem.threshold ?? segmentation.threshold ?? 0.5;
        return v >= th ? 1 : 0;
    }

    return Number((data as Uint8Array)[pixelIdx] ?? 0);
}

function isMultiFeatureRep(rep: string): rep is MultiFeatureRep {
    return rep === "MultiClass" || rep === "MultiLabel";
}

function isIndependentMaskRep(rep: string): rep is IndependentMaskRep {
    return rep === "Binary" || rep === "DualBitMask" || rep === "Probability";
}

/** True when A should run the segmentation pipette. */
export function shouldHandleFeaturePipetteKey(
    event: KeyboardEvent,
    mainViewerContext: MainViewerContext,
    viewerContext: ViewerContext,
): boolean {
    if (event.code !== FEATURE_PIPETTE_KEY || event.repeat) return false;
    if (isTypingTarget(event)) return false;
    if (!mainViewerContext.active) return false;
    return viewerContext.activePanels.has("Segmentation");
}

/** Lowest feature index present at pixel (matches shader layer iteration order). */
export function pickFeatureIndexAtPixel(
    annotation: number,
    dataRepresentation: MultiFeatureRep,
): number | null {
    if (annotation === 0) return null;

    if (dataRepresentation === "MultiClass") {
        return annotation;
    }

    for (let i = 0; i < 32; i++) {
        if ((annotation & (1 << i)) !== 0) {
            return i + 1;
        }
    }
    return null;
}

export function sampleFeatureIndexAtImagePosition(
    segmentationItem: SegmentationItem,
    viewerContext: ViewerContext,
    imagePosition: Position2D,
): number | null {
    const segmentation = segmentationItem.segmentation;
    const rep = segmentation.data_representation;
    if (!isMultiFeatureRep(rep)) return null;

    const mask = segmentationItem.getMask(viewerContext.index);
    if (!mask) return null;

    const pixel = segmentationPixelIndex(
        segmentation,
        viewerContext.image,
        imagePosition,
    );
    if (!pixel) return null;

    const annotation = readAnnotationAtPixel(
        mask,
        segmentation,
        segmentationItem,
        pixel.idx,
    );
    return pickFeatureIndexAtPixel(annotation, rep);
}

function hasIndependentMaskAtPixel(
    segmentationItem: SegmentationItem,
    viewerContext: ViewerContext,
    imagePosition: Position2D,
): boolean {
    const segmentation = segmentationItem.segmentation;
    const rep = segmentation.data_representation;
    if (!isIndependentMaskRep(rep)) return false;

    if (segmentationItem.isEmptyForSlice(viewerContext.index)) {
        return false;
    }

    const mask = segmentationItem.getMask(viewerContext.index);
    if (!mask) return false;

    const pixel = segmentationPixelIndex(
        segmentation,
        viewerContext.image,
        imagePosition,
    );
    if (!pixel) return false;

    return (
        readAnnotationAtPixel(mask, segmentation, segmentationItem, pixel.idx) >
        0
    );
}

function pickIndependentSegmentationAtImagePosition(
    segmentationContext: SegmentationContext,
    viewerContext: ViewerContext,
    userId: number,
    imagePosition: Position2D,
): SegmentationItem | null {
    for (const segmentation of getVisibleSegmentationsTopmostFirst(
        segmentationContext,
        userId,
    )) {
        const rep = segmentation.data_representation;
        if (!isIndependentMaskRep(rep)) continue;

        const item = segmentationContext.getSegmentationItem(segmentation);
        if (!hasIndependentMaskAtPixel(item, viewerContext, imagePosition)) {
            continue;
        }
        return item;
    }
    return null;
}

export function applyFeaturePipette(
    mainViewerContext: MainViewerContext,
    viewerContext: ViewerContext,
    userId: number,
    imagePosition: Position2D,
): boolean {
    const segmentationContext = mainViewerContext.segmentationContext;
    const activeItem = segmentationContext.segmentationItem;

    if (activeItem) {
        const rep = activeItem.segmentation.data_representation;
        if (isMultiFeatureRep(rep)) {
            const featureIndex = sampleFeatureIndexAtImagePosition(
                activeItem,
                viewerContext,
                imagePosition,
            );
            if (featureIndex != null) {
                segmentationContext.activeIndices =
                    rep === "MultiLabel" ? [featureIndex] : featureIndex;
                mainViewerContext.highlightedFeatureIndex = featureIndex;
                mainViewerContext.highlightedSegmentationItem = activeItem;
                viewerContext.repaint();
                return true;
            }
        }
    }

    const picked = pickIndependentSegmentationAtImagePosition(
        segmentationContext,
        viewerContext,
        userId,
        imagePosition,
    );
    if (!picked) return false;

    segmentationContext.activateSegmentationItem(picked);
    mainViewerContext.highlightedSegmentationItem = picked;
    mainViewerContext.highlightedFeatureIndex = undefined;
    viewerContext.repaint();
    return true;
}

export function handleFeaturePipetteKeydown(
    e: ViewerEvent<KeyboardEvent>,
    mainViewerContext: MainViewerContext,
    userId: number,
): boolean {
    if (
        !shouldHandleFeaturePipetteKey(
            e.event,
            mainViewerContext,
            e.viewerContext,
        )
    ) {
        return false;
    }
    return applyFeaturePipette(
        mainViewerContext,
        e.viewerContext,
        userId,
        e.position,
    );
}
