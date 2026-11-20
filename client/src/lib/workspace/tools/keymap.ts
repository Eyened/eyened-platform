import {
    COLOR_RENDER_MODES,
    isRenderModeAvailable,
    type RenderMode,
    type ViewerEvent,
    type ViewerEventListener,
} from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { WorkspaceView } from "$lib/viewer-window/viewerWindowContext.svelte";
import { SIZE_STEP, sizeKey } from "../paint";
import { toolForKey } from "./registry";

/** Digits by physical key, so AZERTY works: 1 Original … 0 Blue. */
export const RENDER_MODE_DIGITS: Record<string, RenderMode> =
    Object.fromEntries(
        COLOR_RENDER_MODES.map((mode, i) => [`Digit${(i + 1) % 10}`, mode]),
    );

const HIDE_OVERLAYS = "h";
const LOCALIZER = "o";
const MAGNIFIER = "m";
const SWAP = "x";
const SIZED = ["brush", "eraser", "enhance"];

/** X: Brush and Eraser are two tools; Polygon and Enhance switch between adding and removing. */
function swap(view: WorkspaceView | undefined): void {
    if (!view) return;
    if (view.armedTool === "brush") view.arm("eraser");
    else if (view.armedTool === "eraser") view.arm("brush");
    else if (view.armedTool === "polygon" || view.armedTool === "enhance")
        view.remove = !view.remove;
}

/** The selected viewport's segmentation state and slice; keys reach the focused viewport, and focus selects it. */
function selectedSegmentation(viewerContext: ViewerContext) {
    const layers =
        viewerContext.viewerWindowContext.viewState?.selectedViewport?.layers;
    return layers
        ? {
              segmentationContext: layers.mainViewerContext.segmentationContext,
              index: layers.viewerContext.index,
          }
        : null;
}

/** A viewport's keys. The viewer forwards only keys pressed while it has focus. */
export class Keymap implements ViewerEventListener {
    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;
        const view = viewerContext.viewerWindowContext.viewState;
        const selected = selectedSegmentation(viewerContext);
        // No key acts while a stroke is drawn; Esc is the tool's, which drops the stroke.
        if (selected?.segmentationContext.isDrawing) return;
        if ((event.ctrlKey || event.metaKey) && !event.altKey) {
            const key = event.key.toLowerCase();
            const redo =
                (key === "y" && event.ctrlKey) ||
                (key === "z" && event.shiftKey);
            if (redo || key === "z") {
                event.preventDefault();
                // Undo acts on the selected viewport's current segmentation, never from a strip tile.
                if (event.repeat || viewerContext.isStripTile || !selected)
                    return;
                if (redo) selected.segmentationContext.redo(selected.index);
                else selected.segmentationContext.undo(selected.index);
                return;
            }
        }
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (event.key === "Escape") {
            // A strip tile only fits its view; a viewport's Esc also acts on its image's distance lines.
            const lines = viewerContext.isStripTile
                ? undefined
                : view?.distanceLinesFor(viewerContext.image.image_id);
            // Esc first drops a half-drawn line; only the next Esc is Display Reset.
            if (lines?.drawing) {
                lines.remove(lines.drawing);
                return;
            }
            // A waiting New › Region box is cancelled before anything resets.
            if (
                !viewerContext.isStripTile &&
                selected?.segmentationContext.regionToolActive
            ) {
                selected.segmentationContext.regionToolActive = false;
                return;
            }
            // Then Esc leaves the keyboard cursor; only the next Esc resets the view.
            if (viewerContext.keyboardCursor.on) {
                viewerContext.keyboardCursor.leave();
                return;
            }
            viewerContext.initTransform();
            lines?.clear();
            return;
        }
        if (event.repeat) return;
        const mode = RENDER_MODE_DIGITS[event.code];
        if (mode) {
            if (
                viewerContext.renderControls &&
                isRenderModeAvailable(
                    viewerContext.image.supportsColorRenderModes,
                    mode,
                )
            )
                viewerContext.renderMode = mode;
            return;
        }
        const key = event.key.toLowerCase();
        if (key === HIDE_OVERLAYS) {
            viewerContext.hideOverlays = true;
            return;
        }
        // Focus in a viewport selects it, so this is the viewport the key was pressed in. A tile selects none.
        if (key === LOCALIZER) {
            if (!viewerContext.isStripTile)
                view?.selectedViewport?.layers?.localizer.toggle();
            return;
        }
        if (key === MAGNIFIER) {
            view?.setMagnifier({ on: !view.magnifier.on });
            return;
        }
        if (key === SWAP) {
            swap(view);
            return;
        }
        if (key === "[" || key === "]") {
            const delta = key === "]" ? 1 : -1;
            const armed = view?.armedTool;
            if (!view || !armed) return;
            if (SIZED.includes(armed)) {
                const size = view.paint[sizeKey(viewerContext.image)];
                view.setSize(
                    viewerContext.image,
                    delta > 0 ? size * SIZE_STEP : size / SIZE_STEP,
                );
            } else if (armed === "circle") view.stepCircle(delta);
            else if (armed === "etdrs") view.etdrsSlot = delta > 0 ? 1 : 0;
            else if (armed === "point") {
                const layers = view.selectedViewport?.layers;
                layers?.pointTool?.step(delta, layers.viewerContext);
            }
            return;
        }
        // A letter does what a click on its button does: the armed tool's key returns to No tool.
        const tool = toolForKey(key);
        if (tool) view?.toggleTool(tool.id);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        if (e.event.key.toLowerCase() === HIDE_OVERLAYS)
            e.viewerContext.hideOverlays = false;
    }
}
