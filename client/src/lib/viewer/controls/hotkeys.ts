import type {
    ViewerEvent,
    ViewerEventListener,
    RenderMode,
} from "../viewer-utils";
import { isRenderModeAvailable } from "../viewer-utils";

export class HotKeys implements ViewerEventListener {
    codes: { [key: string]: RenderMode } = {
        KeyR: "Original",
        KeyL: "Luminance",
        KeyE: "Contrast enhanced",
        KeyB: "Color balanced",
        KeyH: "CLAHE",
        KeyS: "Sharpened",
        KeyM: "Histogram matched",
    };
    constructor() {}

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const {
            event: { code, repeat },
            viewerContext,
        } = e;
        if (repeat) return;

        const hideOverlays = code === "Space";
        viewerContext.hideOverlays = hideOverlays;

        if (code in this.codes) {
            const mode = this.codes[code];
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
