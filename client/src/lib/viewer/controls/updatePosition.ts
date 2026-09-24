import type { ViewerEvent, ViewerEventListener } from "../viewer-utils";

export class UpdatePosition implements ViewerEventListener {
    constructor() {}

    pointermove(e: ViewerEvent<PointerEvent>) {
        const {
            viewerContext,
            viewerContext: { registration, image, index },
            cursor,
        } = e;

        if (!viewerContext.updatePosition) {
            return;
        }
        if (e.event.buttons !== 0) {
            return;
        }

        const isTopViewer =
            viewerContext.viewerWindowContext.topViewers.get(image) ===
            viewerContext;
        // Top viewers require Shift; main viewers always update.
        if (isTopViewer && !e.modifiers.shift) {
            return;
        }

        const imagePosition = viewerContext.viewerToImageCoordinates(cursor);
        registration.setPosition(image.image_id, { ...imagePosition, index });
    }
}
