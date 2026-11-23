import {
    COLOR_RENDER_MODES,
    isRenderModeAvailable,
    type RenderMode,
    type ViewerEvent,
    type ViewerEventListener,
} from "$lib/viewer/viewer-utils";
import { toolForKey } from "./registry";

/** Digits by physical key, so AZERTY works: 1 Original … 0 Blue. */
export const RENDER_MODE_DIGITS: Record<string, RenderMode> =
    Object.fromEntries(
        COLOR_RENDER_MODES.map((mode, i) => [`Digit${(i + 1) % 10}`, mode]),
    );

const HIDE_OVERLAYS = "h";

/** A viewport's keys. The viewer forwards only keys pressed while it has focus. */
export class Keymap implements ViewerEventListener {
    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;
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
        const tool = toolForKey(key);
        if (tool) viewerContext.viewerWindowContext.viewState?.arm(tool.id);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        if (e.event.key.toLowerCase() === HIDE_OVERLAYS)
            e.viewerContext.hideOverlays = false;
    }
}
