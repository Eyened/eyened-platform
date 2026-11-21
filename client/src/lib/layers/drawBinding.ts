import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { ToolId } from "$lib/workspace/tools/registry";

/** What the options bar names for a viewport, and why a Draw tool can't write there; a null reason means it can. */
export interface DrawTarget {
    /** Null when the viewport has no segmentation selected. */
    name: { segmentation: string; feature: string | null } | null;
    /** A one-class segmentation's colour for the bar's chip; null for a class mask, or before it has a colour. */
    color: string | null;
    reason: string | null;
}

/** The viewport's selected segmentation for the armed tool; a Draw tool writes only into it. */
export function drawBinding(input: {
    segmentation: Segmentation | null;
    /** The segmentation's colour as hex, when it has one. */
    color: string | null;
    activeIndices: number | number[];
    toolId: ToolId | null;
    canEdit: (segmentation: Segmentation) => boolean;
}): DrawTarget {
    const s = input.segmentation;
    if (!s)
        return {
            name: null,
            color: null,
            reason: "Select a segmentation to draw",
        };
    const name = {
        segmentation: s.feature.name,
        feature: featureName(s, input.activeIndices),
    };
    const color =
        s.data_representation === "MultiClass" ||
        s.data_representation === "MultiLabel"
            ? null
            : input.color;
    if (s.annotation_type === "model_segmentation")
        return {
            name,
            color,
            reason: "This model segmentation can't be edited. Duplicate it to edit.",
        };
    if (!input.canEdit(s))
        return {
            name,
            color,
            reason: "Another grader's segmentation can't be edited. Duplicate it to edit.",
        };
    if (input.toolId === "enhance" && s.data_representation !== "Probability")
        return {
            name,
            color,
            reason: "Enhance works on probability segmentations only. Choose one in Segmentations.",
        };
    return { name, color, reason: null };
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
