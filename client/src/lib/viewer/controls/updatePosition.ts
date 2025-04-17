import type { ViewerEvent, ViewerEventListener } from "../viewer-utils";

export class UpdatePosition implements ViewerEventListener {

    constructor() { }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (e.event.shiftKey) return;
        const { viewerContext, viewerContext: { registration, image, index }, cursor } = e;

        if (!viewerContext.updatePosition) {
            return;
        }

        const imagePosition = viewerContext.viewerToImageCoordinates(cursor);
        registration.setPosition(image.image_id, { ...imagePosition, index });
    }

}