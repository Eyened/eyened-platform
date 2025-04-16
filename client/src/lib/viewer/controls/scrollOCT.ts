import type { ViewerEvent, ViewerEventListener } from "../viewer-utils";

export class ScrollOCT implements ViewerEventListener {
    scaleSensitivity = 1.1;
    scrollLineHeight = 16;

    constructor() { }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e
        const { lockScroll, image, index } = viewerContext;
        if (lockScroll) return;
        if (event.code === 'ArrowUp') {
            const i = (index - 1 + image.depth) % image.depth;
            viewerContext.setIndex(i);
        }
        if (event.code === 'ArrowDown') {
            const i = (index + 1) % image.depth;
            viewerContext.setIndex(i);
        }
    }

    wheel(e: ViewerEvent<WheelEvent>) {
        const { event, viewerContext } = e
        const { image, lockScroll, index } = viewerContext
        if (event.shiftKey) return;
        if (lockScroll) return;
        const delta = event.deltaY;

        let i = index + Math.sign(delta);
        i = Math.max(0, Math.min(i, image.depth - 1));
        viewerContext.setIndex(i);
    }
}