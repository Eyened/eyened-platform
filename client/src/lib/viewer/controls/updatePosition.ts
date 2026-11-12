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
        // The Cross-hair tool sets the crosshair by click or drag only.
        if (
            viewerContext.viewerWindowContext.viewState?.armedTool ===
            "crosshair"
        )
            return;
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
