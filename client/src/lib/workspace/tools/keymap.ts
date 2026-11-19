import {
    COLOR_RENDER_MODES,
    isRenderModeAvailable,
    type RenderMode,
    type ViewerEvent,
    type ViewerEventListener,
} from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { toolForKey } from "./registry";

/** Digits by physical key, so AZERTY works: 1 Original … 0 Blue. */
export const RENDER_MODE_DIGITS: Record<string, RenderMode> =
    Object.fromEntries(
        COLOR_RENDER_MODES.map((mode, i) => [`Digit${(i + 1) % 10}`, mode]),
    );

const HIDE_OVERLAYS = "h";
const LOCALIZER = "o";
const MAGNIFIER = "m";

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
        // No key acts while a stroke is drawn; Esc is the tool's, which drops the stroke.
        if (selectedSegmentation(viewerContext)?.segmentationContext.isDrawing)
            return;
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (event.key === "Escape") {
            viewerContext.initTransform();
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
                viewerContext.viewerWindowContext.viewState?.selectedViewport?.layers?.localizer.toggle();
            return;
        }
        if (key === MAGNIFIER) {
            const view = viewerContext.viewerWindowContext.viewState;
            view?.setMagnifier({ on: !view.magnifier.on });
            return;
        }
        const tool = toolForKey(key);
        if (tool) viewerContext.viewerWindowContext.viewState?.arm(tool.id);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        if (e.event.key.toLowerCase() === HIDE_OVERLAYS)
            e.viewerContext.hideOverlays = false;
    }
}
