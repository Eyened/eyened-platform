import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import { colors } from "$lib/viewer/overlays/colors";
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
        const renderAsHeatmap = mode === "heatmap";

        for (const { projection, color, layerAlpha } of projections) {
            const layerColor = color ?? colors[0];
            viewerContext.image.webgl.shaders.renderEnfaceProjection.pass(
                renderTarget,
                {
                    ...uniforms,
                    u_thickness: projection.textureData.texture,
                    u_color: layerColor.map((c) => c / 255),
                    u_max_thickness: renderAsHeatmap
                        ? projection.getMaxThickness()
                        : 1,
                    u_alpha: layerAlpha * this.mainViewerContext.alpha,
                    u_mode: renderAsHeatmap ? 1 : 0,
                    u_outline: false,
                },
            );
        }
    }
}
