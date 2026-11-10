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

        // Strip tiles never write the shared pointer, so hovering one moves nothing else.
        if (
            viewerContext.viewerWindowContext.topViewers.get(image) ===
            viewerContext
        ) {
            return;
        }

        const imagePosition = viewerContext.viewerToImageCoordinates(cursor);
        registration.setPosition(image.image_id, { ...imagePosition, index });
    }
}
