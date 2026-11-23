import type { ViewerEvent, ViewerEventListener } from "../viewer-utils";

export class ScrollOCT implements ViewerEventListener {
    scaleSensitivity = 1.1;
    scrollLineHeight = 16;

    constructor() {}

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;
        const { lockScroll, image, index } = viewerContext;
        if (lockScroll || viewerContext.sliceLocked) return;
        if (event.code === "ArrowUp" && index > 0)
            viewerContext.setIndex(index - 1);
        if (event.code === "ArrowDown" && index < image.depth - 1)
            viewerContext.setIndex(index + 1);
    }

    wheel(e: ViewerEvent<WheelEvent>) {
        const { viewerContext, wheel } = e;
        const { image, lockScroll, index } = viewerContext;
        if (wheel?.zoomIntent) return;
        if (lockScroll || viewerContext.sliceLocked) return;
        const delta = wheel?.primaryDeltaPx ?? 0;

        let i = index + Math.sign(delta);
        i = Math.max(0, Math.min(i, image.depth - 1));
        viewerContext.setIndex(i);
    }
}
