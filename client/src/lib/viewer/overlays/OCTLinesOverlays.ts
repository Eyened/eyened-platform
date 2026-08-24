import type { PhotoLocator } from "$lib/registration/photoLocators";
import type { Overlay } from "../viewer-utils";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerContext } from "../viewerContext.svelte";

export class OCTLinesOverlay implements Overlay {

    constructor(readonly photolocators: PhotoLocator[]) { }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const { context2D, image } = viewerContext;

        // const pointer = viewerContext.registration.pointer;
        context2D.lineWidth = 0.5;
        for (const locator of this.photolocators) {
            // console.log(locator.enfaceImageId, image.image_id, locator.enfaceImageId == image.image_id);
            if (locator.enfaceImageId == image.image_id) {
                // const octPosition = pointer[locator.octImageId];
                const octPosition = viewerContext.registration.getPosition(locator.octImageId);
                if (octPosition?.index == locator.index) {
                    context2D.strokeStyle = 'rgba(255,255,255,1)';
                } else {
                    context2D.strokeStyle = 'rgba(0,255,0,0.2)';
                }
                locator.paint(context2D, viewerContext);
            }
        }

    }
}