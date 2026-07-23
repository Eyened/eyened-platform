import type {
    Segmentation,
    SegmentationContext,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { colors } from "$lib/viewer/overlays/colors";
import type { Color } from "$lib/utils";

import { SIMPLE_ENFACE_FEATURE_INDEX } from "$lib/webgl/enfaceProjectionConstants";

export { SIMPLE_ENFACE_FEATURE_INDEX };

export function getEnfaceLayerKey(
    segmentationKey: string,
    featureIndex: number,
): string {
    return `${segmentationKey}#${featureIndex}`;
}

export function getSubfeatureIndices(segmentation: Segmentation): number[] {
    return (segmentation.feature.subfeatures ?? []).map(
        (subfeature) => subfeature.index,
    );
}

/** Color for a MC/ML subfeature index (matches fs_render_multi_class indexing). */
export function getSubfeatureColor(featureIndex: number): Color {
    const colorIndex =
        featureIndex > 0
            ? (featureIndex - 1) % colors.length
            : featureIndex % colors.length;
    return colors[colorIndex] ?? colors[0];
}

export function isProjectable(segmentation: Segmentation): boolean {
    if (segmentation.image_projection_matrix) {
        return false;
    }

    const rep = segmentation.data_representation;
    if (
        rep === "Binary" ||
        rep === "DualBitMask" ||
        rep === "Probability"
    ) {
        return true;
    }

    if (rep === "MultiClass" || rep === "MultiLabel") {
        return getSubfeatureIndices(segmentation).length > 0;
    }

    return false;
}

/** Subfeature indices for MC/ML; otherwise the single simple layer index. */
export function getEnfaceFeatureIndices(segmentation: Segmentation): number[] {
    const rep = segmentation.data_representation;
    if (rep === "MultiClass" || rep === "MultiLabel") {
        return getSubfeatureIndices(segmentation);
    }
    return [SIMPLE_ENFACE_FEATURE_INDEX];
}

export function isMultiFeatureEnfaceSegmentation(
    segmentation: Segmentation,
): boolean {
    const rep = segmentation.data_representation;
    return rep === "MultiClass" || rep === "MultiLabel";
}

/** Bit for a 1-based subfeature index (matches segmentationContext / B-scan shaders). */
function getSubfeatureBit(featureIndex: number): number {
    return featureIndex > 0
        ? ((1 << (featureIndex - 1)) >>> 0)
        : (1 >>> 0);
}

/** Active-feature mask for MC/ML (same as MultiClassMask / MultiLabelMask.getBitmask). */
export function getActiveFeatureMask(
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
            bitmask |= getSubfeatureBit(index);
        }
        return bitmask >>> 0;
    }

    return getSubfeatureBit(activeIndices);
}

/** Whether an enface layer passes the subfeature eye toggle (u_visible_feature_mask). */
export function isEnfaceLayerVisible(
    segmentation: Segmentation,
    featureIndex: number,
    segmentationContext: SegmentationContext,
): boolean {
    if (!isMultiFeatureEnfaceSegmentation(segmentation)) {
        return true;
    }

    return segmentationContext.isFeatureLayerVisible(segmentation, featureIndex);
}

/**
 * Per-layer opacity matching fs_render_multi_class / fs_render_multi_label
 * before the final multiply with u_alpha.
 */
export function getEnfaceLayerAlpha(
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
    const featureBit = getSubfeatureBit(featureIndex);

    if (rep === "MultiClass") {
        const showHighlight =
            highlighted || activeMask === featureIndex;
        return showHighlight
            ? segmentationContext.multiClassActiveAlpha
            : segmentationContext.multiClassInactiveAlpha;
    }

    // MultiLabel: default inactive weight 0.1, active/highlight 1.0
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
