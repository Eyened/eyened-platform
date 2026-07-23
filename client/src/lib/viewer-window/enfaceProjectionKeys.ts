import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

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
