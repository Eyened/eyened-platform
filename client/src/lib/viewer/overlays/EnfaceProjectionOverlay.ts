import type { EnfaceOverlaySourceResolved } from "$lib/registration/resolveEnfaceOverlaySources";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import { ShaderTemplateCache } from "$lib/webgl/shaderTemplate";
import type { RenderTarget } from "$lib/webgl/types";
import fs_render_enface_projection from "./fs_render_enface_projection.frag";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import type { MainViewerContext } from "./MainViewerContext.svelte";

export type EnfaceOverlayPaintSource = EnfaceOverlaySourceResolved & {
    mainViewerContext: MainViewerContext;
};

export class EnfaceProjectionOverlay implements Overlay {
    private readonly programs = new ShaderTemplateCache();

    constructor(readonly sources: EnfaceOverlayPaintSource[]) {}

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget): void {
        const base = getBaseUniforms(viewerContext);

        for (const source of this.sources) {
            if (source.mode === "off" || !source.mainViewerContext) {
                continue;
            }

            let program;
            try {
                program = this.programs.getOrCompile(
                    viewerContext.image.webgl,
                    fs_render_enface_projection,
                    { mapping: source.mappingGlsl },
                );
            } catch {
                continue;
            }

            const projections = source.manager.getVisibleProjections();
            if (!projections.length) {
                continue;
            }

            const renderAsHeatmap = source.mode === "heatmap";
            for (const { projection, color, layerAlpha } of projections) {
                const thicknessRange = renderAsHeatmap
                    ? projection.getThicknessRange()
                    : { min: 0, max: 1 };
                program.pass(renderTarget, {
                    ...base,
                    u_thickness: projection.textureData.texture,
                    u_color: color.map((c) => c / 255),
                    u_min_thickness: thicknessRange.min,
                    u_max_thickness: thicknessRange.max,
                    u_alpha: layerAlpha * source.mainViewerContext.alpha,
                    u_mode: renderAsHeatmap ? 1 : 0,
                    u_outline: false,
                    u_size_primary: source.sizePrimary,
                    u_size_secondary: source.sizeSecondary,
                });
            }
        }
    }
}
