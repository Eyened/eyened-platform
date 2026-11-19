import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { ToolId } from "$lib/workspace/tools/registry";

/** What the options bar names for a viewport, and why a Draw tool can't write there; a null reason means it can. */
export interface DrawTarget {
    /** Null when the viewport has no current segmentation. */
    name: { segmentation: string; feature: string | null } | null;
    reason: string | null;
}

/** The viewport's current segmentation for the armed tool; a Draw tool writes only into it. */
export function drawBinding(input: {
    segmentation: Segmentation | null;
    activeIndices: number | number[];
    toolId: ToolId | null;
    canEdit: (segmentation: Segmentation) => boolean;
}): DrawTarget {
    const s = input.segmentation;
    if (!s)
        return {
            name: null,
            reason: "No current segmentation. Choose one in Segmentations.",
        };
    const name = {
        segmentation: s.feature.name,
        feature: featureName(s, input.activeIndices),
    };
    if (s.annotation_type === "model_segmentation")
        return {
            name,
            reason: "This model segmentation can't be edited. Duplicate it to edit.",
        };
    if (!input.canEdit(s))
        return {
            name,
            reason: "Another grader's segmentation can't be edited. Duplicate it to edit.",
        };
    if (input.toolId === "enhance" && s.data_representation !== "Probability")
        return {
            name,
            reason: "Enhance works on probability segmentations only. Choose one in Segmentations.",
        };
    return { name, reason: null };
}

/** The class a MultiClass or MultiLabel segmentation draws; null for a one-class segmentation. */
function featureName(
    segmentation: Segmentation,
    active: number | number[],
): string | null {
    const indices = Array.isArray(active) ? active : [active];
    const names = (segmentation.feature.subfeatures ?? [])
        .filter((f) => indices.includes(f.index))
        .map((f) => f.name);
    return names.length ? names.join(", ") : null;
}
