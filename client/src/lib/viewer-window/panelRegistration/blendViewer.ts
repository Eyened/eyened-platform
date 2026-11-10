import { instances } from "$lib/data";
import Viewer from "$lib/viewer/Viewer.svelte";
import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { BlendLayerStyle } from "$lib/webgl/blendRenderer";
import type { ImageRenderer } from "$lib/webgl/imageRenderer";
import { mount, unmount } from "svelte";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

/**
 * Viewer reads its context once, so a new anchor image needs a new
 * ViewerContext and a remount. Returns the unmount.
 */
export function mountBlendViewer(
    target: HTMLElement,
    anchor: AbstractImage,
    viewerWindowContext: ViewerWindowContext,
    renderer: ImageRenderer,
): () => void {
    const viewerContext = new ViewerContext(anchor, viewerWindowContext);
    viewerContext.imageRenderer =
        renderer as unknown as typeof viewerContext.imageRenderer;
    const app = mount(Viewer, {
        target,
        props: { foreground: true },
        intro: false,
        context: new Map<string, unknown>([
            ["viewerContext", viewerContext],
            ["viewerWindowContext", viewerWindowContext],
        ]),
    });
    return () => void unmount(app);
}

/** Size of an open image, or of its instance when it is only on a path. */
export function registeredImageSize(
    viewerWindowContext: ViewerWindowContext,
    imageId: string,
): [number, number] | undefined {
    for (const image of viewerWindowContext.topViewers.keys()) {
        if (image.image_id === imageId) {
            return [image.width, image.height];
        }
    }
    const instance = instances.get(imageId);
    if (instance && instance.columns > 0 && instance.rows > 0) {
        return [instance.columns, instance.rows];
    }
    return undefined;
}

export function defaultBlendStyle(
    colour: string,
    tint: number,
): BlendLayerStyle {
    return {
        renderMode: "Original",
        windowLevel: { min: 0, max: 255 },
        tint,
        colour,
        opacity: 1,
    };
}
