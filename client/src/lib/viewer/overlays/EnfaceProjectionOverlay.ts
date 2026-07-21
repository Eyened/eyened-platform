import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import type { MainViewerContext } from "./MainViewerContext.svelte";

export class EnfaceProjectionOverlay implements Overlay {
    constructor(
        readonly manager: EnfaceProjectionManager,
        readonly mainViewerContext: MainViewerContext,
    ) {}

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget): void {
        const mode = viewerContext.enfaceProjectionMode;
        if (mode === "off") {
            return;
        }

        const projections = this.manager.getVisibleProjections();
        if (!projections.length) {
            return;
        }

        const uniforms = getBaseUniforms(viewerContext);
        const u_mode = mode === "binary" ? 0 : 1;

        for (const { segmentation, projection } of projections) {
            viewerContext.image.webgl.shaders.renderEnfaceProjection.pass(
                renderTarget,
                {
                    ...uniforms,
                    u_thickness: projection.textureData.texture,
                    u_color: this.mainViewerContext
                        .getFeatureColor(segmentation)
                        .map((c) => c / 255),
                    u_max_thickness:
                        mode === "heatmap" ? projection.getMaxThickness() : 1,
                    u_alpha: this.mainViewerContext.alpha,
                    u_mode,
                    u_outline: false,
                },
            );
        }
    }
}
