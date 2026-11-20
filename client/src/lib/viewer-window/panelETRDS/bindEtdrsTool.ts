import { formAnnotations, setFormAnnotationValue } from "$lib/data";
import type { ImagePoint, PointList } from "$lib/forms/pointSchema";
import { keepGridSize } from "$lib/layers/gridLayers.svelte";
import { ETDRS_LANDMARK_COLOUR } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

const SLOTS = ["fovea", "disc_edge"] as const;

function isImagePoint(value: unknown): value is ImagePoint {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof (value as ImagePoint).x === "number" &&
        typeof (value as ImagePoint).y === "number"
    );
}

/** A grid's fovea and disc edge as a two-slot point list. */
function landmarksOf(formData: unknown): PointList {
    const data = (formData ?? {}) as Record<string, unknown>;
    return SLOTS.map((slot) => {
        const value = data[slot];
        return isImagePoint(value) ? value : null;
    });
}

/** Place ETDRS on one viewer for a grid it may write: a two-slot point tool that saves on release. */
export function bindEtdrsTool(args: {
    viewerContext: ViewerContext;
    gridId: number;
    keepSize: () => boolean;
}): {
    tool: PointTool;
    dispose: () => void;
    sync: (formData: unknown) => void;
} {
    // Every write of this tool, so a saved write coming back from the store is not taken back mid-drag.
    const written = new WeakSet<object>();
    const write = (points: PointList, persist: boolean) => {
        const grid = formAnnotations.get(args.gridId);
        if (!grid) return;
        const data = { ...(grid.form_data as Record<string, unknown>) };
        SLOTS.forEach((slot, i) => {
            const point = points[i];
            if (point == null) delete data[slot];
            else data[slot] = point;
        });
        written.add(data);
        formAnnotations.set(args.gridId, { ...grid, form_data: data });
        if (persist) void setFormAnnotationValue(args.gridId, data);
    };
    // The points before the latest change, so Keep grid size can move the disc edge by the fovea's step.
    let before: PointList = landmarksOf(
        formAnnotations.get(args.gridId)?.form_data,
    );
    const tool: PointTool = new PointTool({
        canEdit: true,
        pointStyle: "cross",
        radius: 16,
        color: ETDRS_LANDMARK_COLOUR,
        cardinality: "list",
        sparse: true,
        // Fovea and disc edge are en-face 2D landmarks, without a B-scan index.
        coordinateSpace: "enface2d",
        slotLabels: ["Fovea", "Disc edge"],
        onChange: (points) => {
            const next = args.keepSize()
                ? keepGridSize(before, points)
                : points;
            if (next !== points) tool.points = next;
            before = next;
            write(next, false);
        },
        // Saving the tool's own points is defensive; they already hold any Keep grid size adjustment.
        onPersist: () => write(tool.points, true),
    });
    tool.points = before;
    const remove = args.viewerContext.addOverlay(tool);
    return {
        tool,
        dispose: () => {
            tool.destroy();
            remove();
        },
        // Another viewport's edit of this grid, so this tool's next edit starts from it.
        sync: (formData) => {
            if (
                typeof formData === "object" &&
                formData !== null &&
                written.has(formData)
            )
                return;
            before = landmarksOf(formData);
            tool.points = before;
        },
    };
}
