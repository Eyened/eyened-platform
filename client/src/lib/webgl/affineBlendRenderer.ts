import { Matrix } from "$lib/matrix";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "./abstractImage";
import { TextureShaderProgram } from "./FragmentShaderProgram";
import fs_registrationBlend from "./glsl/fs_registration_blend.frag";
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";
import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";

/**
 * Two-image blend. The program is compiled once. Point drags only replace
 * `u_affine`.
 */
export type Rgb = readonly [number, number, number];

/** `#rrggbb` to 0–1 channels. Anything else is black. */
export function parseHexColour(hex: string): Rgb {
    const match = /^#?([0-9a-fA-F]{6})$/.exec(hex.trim());
    if (!match) return [0, 0, 0];
    const value = Number.parseInt(match[1]!, 16);
    return [
        (value >> 16) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    ];
}

export class AffineBlendRenderer implements ImageRenderer {
    private readonly shader: TextureShaderProgram;
    private fixed: AbstractImage | null = null;
    private overlay: AbstractImage | null = null;
    private affine: Matrix = Matrix.identity;
    private fixedMix = 1;
    private overlayMix = 1;
    private fixedOpacity = 1;
    private overlayOpacity = 1;
    private fixedColour: Rgb = [1, 0, 0];
    private overlayColour: Rgb = [0, 1, 1];

    constructor(webgl: WebGL) {
        this.shader = new TextureShaderProgram(webgl, fs_registrationBlend);
    }

    setPair(
        fixed: AbstractImage,
        overlay: AbstractImage | null,
        affine: Matrix | null,
    ) {
        this.fixed = fixed;
        this.overlay = overlay;
        this.affine = affine ?? Matrix.identity;
    }

    /** `mix` is 0 for the original colours and 1 for luminosity times `colour`. */
    setTint(
        fixedMix: number,
        fixedColour: Rgb,
        fixedOpacity: number,
        overlayMix: number,
        overlayColour: Rgb,
        overlayOpacity: number,
    ) {
        this.fixedMix = fixedMix;
        this.fixedColour = fixedColour;
        this.fixedOpacity = fixedOpacity;
        this.overlayMix = overlayMix;
        this.overlayColour = overlayColour;
        this.overlayOpacity = overlayOpacity;
    }

    dispose() {
        this.shader.dispose();
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const fixed = this.fixed;
        if (!fixed) return;
        const overlay = this.overlay ?? fixed;
        const uniforms = getBaseUniforms(viewerContext);
        uniforms.u_fixed = fixed.texture;
        uniforms.u_overlay = overlay.texture;
        uniforms.u_size_fixed = [fixed.width, fixed.height];
        uniforms.u_size_overlay = [overlay.width, overlay.height];
        uniforms.u_affine = this.affine.asUniform;
        uniforms.u_has_overlay = this.overlay ? 1 : 0;
        uniforms.u_fixed_mix = this.fixedMix;
        uniforms.u_overlay_mix = this.overlayMix;
        uniforms.u_fixed_opacity = this.fixedOpacity;
        uniforms.u_overlay_opacity = this.overlayOpacity;
        uniforms.u_fixed_colour = [...this.fixedColour];
        uniforms.u_overlay_colour = [...this.overlayColour];
        this.shader.pass(renderTarget, uniforms);
    }
}
