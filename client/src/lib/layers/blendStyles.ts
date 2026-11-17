import { instances } from "$lib/data";
import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
import type { BlendLayerStyle } from "$lib/webgl/blendRenderer";
import { SvelteMap } from "svelte/reactivity";

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

/** An image's part in a blend: this viewport's image, the image paired with it, or a series image. */
export type BlendRole = "this" | "other" | "series";

/** #273's starting looks: this image red, the other cyan, series images untinted. */
export function defaultBlendStyle(role: BlendRole): BlendLayerStyle {
    return {
        renderMode: "Original",
        windowLevel: { min: 0, max: 255 },
        tint: role === "series" ? 0 : 1,
        colour:
            role === "this"
                ? "#ff0000"
                : role === "other"
                  ? "#00ffff"
                  : "#ffffff",
        opacity: 1,
        invert: false,
    };
}

/** Blend looks for the page session, per image and role; nothing is saved. */
export class BlendStyles {
    private readonly styles = new SvelteMap<string, BlendLayerStyle>();

    get(imageId: string, role: BlendRole): BlendLayerStyle {
        return this.styles.get(`${imageId}|${role}`) ?? defaultBlendStyle(role);
    }

    set(
        imageId: string,
        role: BlendRole,
        change: Partial<BlendLayerStyle>,
    ): void {
        this.styles.set(`${imageId}|${role}`, {
            ...this.get(imageId, role),
            ...change,
        });
    }

    reset(imageId: string, role: BlendRole): void {
        this.styles.delete(`${imageId}|${role}`);
    }
}
