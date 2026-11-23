import { vi } from "vitest";
import { Matrix } from "$lib/matrix";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
import { ViewerContext } from "./viewerContext.svelte";

export type ImageKind = "colour" | "grey" | "bscan" | "enface";

/** A synthetic 128-slice volume or 2D image; only what ViewerContext and the controls read. */
function fakeImage(kind: ImageKind): AbstractImage {
    const volume = kind === "bscan" || kind === "enface";
    return {
        image_id: `img-${kind}`,
        instance: { id: 1, device: { model: "Synthetic" } },
        width: 512,
        height: 512,
        depth: volume ? 128 : 1,
        is3D: volume,
        is2D: !volume,
        orientation: kind === "bscan" ? "axial" : "enface",
        supportsColorRenderModes: kind === "colour",
        resolution: { x: 10, y: 5, z: 30 },
        transform: Matrix.identity,
        webgl: { shaders: {} },
    } as unknown as AbstractImage;
}

/** A real ViewerContext on a synthetic image and a fake window. Mock `$lib/webgl/imageRenderer` in the test file. */
export function viewerOf(kind: ImageKind): ViewerContext {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const registration = { getPosition: vi.fn(), setPosition: vi.fn() };
    return new ViewerContext(fakeImage(kind), {
        registration,
    } as unknown as ViewerWindowContext);
}
