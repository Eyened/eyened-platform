import { instances } from "$lib/data";
import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";

/** Size of an open image, or of its instance when it is only on a path. */
export function registeredImageSize(
    win: Pick<ViewerWindowContext, "topViewers">,
    imageId: string,
): [number, number] | undefined {
    for (const image of win.topViewers.keys()) {
        if (image.image_id === imageId) return [image.width, image.height];
    }
    const instance = instances.get(imageId);
    if (instance && instance.columns > 0 && instance.rows > 0) {
        return [instance.columns, instance.rows];
    }
    return undefined;
}
