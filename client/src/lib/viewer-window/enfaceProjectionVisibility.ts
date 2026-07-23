import {
    getSegmentationKey,
    type Segmentation,
    type SegmentationContext,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import {
    getEnfaceFeatureIndices,
    isMultiFeatureEnfaceSegmentation,
    isProjectable,
} from "$lib/viewer-window/enfaceProjectionKeys";
import { subfeatureBit } from "$lib/viewer-window/panelSegmentation/subfeatureBits";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { colors } from "$lib/viewer/overlays/colors";
import type { Color } from "$lib/utils";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";

export type EnfaceLayerCandidate = {
    segmentation: Segmentation;
    segmentationItem: SegmentationItem;
    featureIndex: number;
    layerAlpha: number;
    color: Color;
};

function getSubfeatureColor(featureIndex: number): Color {
    const colorIndex =
        featureIndex > 0
            ? (featureIndex - 1) % colors.length
            : featureIndex % colors.length;
    return colors[colorIndex] ?? colors[0];
}

function getActiveFeatureMask(
    segmentation: Segmentation,
    activeIndices: number | number[],
): number {
    if (segmentation.data_representation === "MultiClass") {
        if (Array.isArray(activeIndices)) {
            return 0;
        }
        return activeIndices;
    }

    if (Array.isArray(activeIndices)) {
        let bitmask = 0;
        for (const index of activeIndices) {
            bitmask |= subfeatureBit(index);
        }
        return bitmask >>> 0;
    }

    return subfeatureBit(activeIndices);
}

function isEnfaceLayerVisible(
    segmentation: Segmentation,
    featureIndex: number,
    segmentationContext: SegmentationContext,
): boolean {
    if (!isMultiFeatureEnfaceSegmentation(segmentation)) {
        return true;
    }

    return segmentationContext.isFeatureLayerVisible(segmentation, featureIndex);
}

function getEnfaceLayerAlpha(
    segmentation: Segmentation,
    featureIndex: number,
    segmentationContext: SegmentationContext,
    highlightedFeatureIndex: number | undefined,
): number {
    if (!isMultiFeatureEnfaceSegmentation(segmentation)) {
        return 1;
    }

    const rep = segmentation.data_representation;
    const highlighted = highlightedFeatureIndex === featureIndex;
    const activeMask = getActiveFeatureMask(
        segmentation,
        segmentationContext.activeIndices,
    );
    const featureBit = subfeatureBit(featureIndex);

    if (rep === "MultiClass") {
        const showHighlight = highlighted || activeMask === featureIndex;
        return showHighlight
            ? segmentationContext.multiClassActiveAlpha
            : segmentationContext.multiClassInactiveAlpha;
    }

    let layerAlpha = 0.1;
    if (!segmentationContext.isDrawing) {
        if (highlighted) {
            layerAlpha = 1;
        }
        if ((activeMask & featureBit) > 0) {
            layerAlpha = 1;
        }
    }
    return layerAlpha;
}

export function getEnfaceLayerColor(
    segmentation: Segmentation,
    mainViewerContext: MainViewerContext | undefined,
    featureIndex: number,
): Color {
    if (isMultiFeatureEnfaceSegmentation(segmentation)) {
        return getSubfeatureColor(featureIndex);
    }

    return mainViewerContext?.getFeatureColor(segmentation) ?? colors[0];
}

export function enumerateVisibleEnfaceLayers(
    ctx: SegmentationContext,
    mainViewerContext: MainViewerContext | undefined,
    attachedItems: ReadonlyMap<string, SegmentationItem>,
): EnfaceLayerCandidate[] {
    if (!mainViewerContext) {
        return [];
    }

    const result: EnfaceLayerCandidate[] = [];

    for (const segmentation of [
        ...ctx.visibleGraderSegmentations,
        ...ctx.visibleModelSegmentations,
    ]) {
        if (!isProjectable(segmentation)) {
            continue;
        }

        const segmentationKey = getSegmentationKey(segmentation);
        const segmentationItem = ctx.getSegmentationItem(segmentation);
        if (!attachedItems.has(segmentationKey)) {
            continue;
        }

        for (const featureIndex of getEnfaceFeatureIndices(segmentation)) {
            if (!isEnfaceLayerVisible(segmentation, featureIndex, ctx)) {
                continue;
            }

            const layerAlpha = getEnfaceLayerAlpha(
                segmentation,
                featureIndex,
                ctx,
                mainViewerContext.highlightedFeatureIndex,
            );
            if (layerAlpha <= 0) {
                continue;
            }

            result.push({
                segmentation,
                segmentationItem,
                featureIndex,
                layerAlpha,
                color: getEnfaceLayerColor(
                    segmentation,
                    mainViewerContext,
                    featureIndex,
                ),
            });
        }
    }

    return result;
}
