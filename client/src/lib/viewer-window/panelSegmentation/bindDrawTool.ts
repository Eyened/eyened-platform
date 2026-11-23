import { BrushTool } from "$lib/viewer/tools/Brush";
import { EnhanceTool } from "$lib/viewer/tools/Enhance.svelte";
import { PolygonTool } from "$lib/viewer/tools/Polygon";
import type { PaintView } from "$lib/viewer/tools/segmentation";
import { SetBrushRadiusTool } from "$lib/viewer/tools/setBrushRadius";
import { NoEditCursor } from "$lib/viewer/tools/viewTools";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { ToolId } from "$lib/workspace/tools/registry";
import type { SegmentationContext } from "./segmentationContext.svelte";

/** Mounts the armed Draw tool on one viewer, or the "can't edit" cursor. The returned function writes any stroke in progress and removes them. */
export function bindDrawTool(input: {
    toolId: ToolId;
    editable: boolean;
    viewerContext: ViewerContext;
    segmentationContext: SegmentationContext;
    workspace: PaintView;
    report: (message: string | null) => void;
}): () => void {
    const { toolId, viewerContext, workspace } = input;
    if (!input.editable) {
        const remove = viewerContext.addOverlay(new NoEditCursor());
        return () => {
            remove();
            viewerContext.resetCursor();
        };
    }
    const deps = {
        viewerContext,
        segmentationContext: input.segmentationContext,
        view: workspace,
        report: input.report,
    };
    const tool =
        toolId === "polygon"
            ? new PolygonTool(deps)
            : toolId === "enhance"
              ? new EnhanceTool(deps)
              : new BrushTool(deps, toolId === "eraser" ? "erase" : "paint");
    const removers = [viewerContext.addOverlay(tool)];
    if (toolId !== "polygon")
        removers.push(
            viewerContext.addOverlay(
                new SetBrushRadiusTool(
                    viewerContext,
                    workspace,
                    () =>
                        toolId === "eraser" ||
                        (toolId === "enhance" && workspace.remove),
                ),
            ),
        );
    return () => {
        tool.endDraw(viewerContext);
        for (const remove of removers) remove();
        viewerContext.resetCursor();
    };
}
