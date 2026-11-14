import type { EnfaceOverlaySourceResolved } from "$lib/registration/resolveEnfaceOverlaySources";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import { compileShaderTemplate } from "$lib/webgl/shaderTemplate";
import type { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { WebGL } from "$lib/webgl/webgl";
import type { RenderTarget } from "$lib/webgl/types";
import { colorsFlat } from "./colors";
import fs_render_enface_projection from "./fs_render_enface_projection.frag";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import type { MainViewerContext } from "./MainViewerContext.svelte";

export type EnfaceOverlayPaintSource = EnfaceOverlaySourceResolved & {
    mainViewerContext: MainViewerContext;
};

type PreparedSource = {
    source: EnfaceOverlayPaintSource;
    program: TextureShaderProgram;
};

/**
 * Programs are compiled once when the overlay is created. StripViewer rebuilds
 * this overlay when registration / modes change, so repaint only draws.
 */
export class EnfaceProjectionOverlay implements Overlay {
    private readonly prepared: PreparedSource[] = [];

    constructor(sources: EnfaceOverlayPaintSource[], webgl: WebGL) {
        for (const source of sources) {
            if (source.mode === "off" || !source.mainViewerContext) {
                continue;
            }
            try {
                const program = compileShaderTemplate(
                    webgl,
                    fs_render_enface_projection,
                    { mapping: source.mappingGlsl },
                );
                this.prepared.push({ source, program });
            } catch (err) {
                console.error(
                    "EnfaceProjectionOverlay: shader compile failed",
                    err,
                );
            }
        }
    }

    /** Release GL programs allocated for this overlay (call on effect teardown). */
    destroy(): void {
        for (const { program } of this.prepared) {
            program.dispose();
        }
        this.prepared.length = 0;
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget): void {
        if (!this.prepared.length) {
            return;
        }

        const base = getBaseUniforms(viewerContext);

        for (const { source, program } of this.prepared) {
            const renderAsHeatmap = source.mode === "heatmap";
            const common = {
                ...base,
                u_outline: false,
                u_size_primary: source.sizePrimary,
                u_size_secondary: source.sizeSecondary,
            };
            for (const layer of source.manager.getPaintLayers(source.mode)) {
                if (layer.kind === "classMap") {
                    // Class numbers: always nearest, linked or not; opacity per class in the shader.
                    program.pass(renderTarget, {
                        ...common,
                        u_thickness: layer.texture,
                        u_colors: colorsFlat,
                        u_active_class: layer.active,
                        u_multi_active_alpha: layer.activeAlpha,
                        u_multi_inactive_alpha: layer.inactiveAlpha,
                        u_alpha: source.mainViewerContext.alpha,
                        u_mode: 2,
                        u_nearest_sample: 1,
                    });
                    continue;
                }
                const { projection, color, layerAlpha } = layer;
                const thicknessRange = renderAsHeatmap
                    ? projection.getThicknessRange()
                    : { min: 0, max: 1 };
                program.pass(renderTarget, {
                    ...common,
                    u_thickness: projection.textureData.texture,
                    u_color: color.map((c) => c / 255),
                    u_min_thickness: thicknessRange.min,
                    u_max_thickness: thicknessRange.max,
                    u_alpha: layerAlpha * source.mainViewerContext.alpha,
                    u_mode: renderAsHeatmap ? 1 : 0,
                    // Nearest only for identity `_proj` binary — avoid LINEAR row bleed.
                    u_nearest_sample:
                        source.identityMapping && !renderAsHeatmap ? 1 : 0,
                });
            }
        }
    }
}
