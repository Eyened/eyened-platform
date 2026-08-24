import type { ViewerEvent, ViewerEventListener, RenderMode } from "../viewer-utils";

export class HotKeys implements ViewerEventListener {
    codes: { [key: string]: RenderMode } = {
        'KeyR': 'Original',
        'KeyL': 'Luminance',
        'KeyE': 'Contrast enhanced',
        'KeyB': 'Color balanced',
        'KeyH': 'CLAHE',
        'KeyS': 'Sharpened',
        'KeyM': 'Histogram matched',
    };
    constructor() { }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        let {
            event: { code, repeat },
            viewerContext: { hideOverlays },
            viewerContext

        } = e;
        if (repeat) return;

        hideOverlays = code === 'Space';
        viewerContext.hideOverlays = hideOverlays;

        if (code in this.codes) {
            viewerContext.renderMode = this.codes[code];
        }

    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { viewerContext } = e;
        viewerContext.hideOverlays = false;
    }
}