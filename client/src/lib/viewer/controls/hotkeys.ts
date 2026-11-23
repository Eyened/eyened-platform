import type {
    ViewerEvent,
    ViewerEventListener,
    RenderMode,
} from "../viewer-utils";
import { isRenderModeAvailable } from "../viewer-utils";

export const RENDER_MODE_CODES: { [code: string]: RenderMode } = {
    KeyR: "Original",
    KeyL: "Luminance",
    KeyE: "Contrast enhanced",
    KeyB: "Color balanced",
    KeyH: "CLAHE",
    KeyS: "Sharpened",
    KeyM: "Histogram matched",
};

export class HotKeys implements ViewerEventListener {
    constructor() {}

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const {
            event: { code, repeat },
            viewerContext,
        } = e;
        if (repeat) return;

        const hideOverlays = code === "Space";
        viewerContext.hideOverlays = hideOverlays;

        if (viewerContext.renderControls && code in RENDER_MODE_CODES) {
            const mode = RENDER_MODE_CODES[code];
            if (
                isRenderModeAvailable(
                    viewerContext.image.supportsColorRenderModes,
                    mode,
                )
            ) {
                viewerContext.renderMode = mode;
            }
        }
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { viewerContext } = e;
        viewerContext.hideOverlays = false;
    }
}
