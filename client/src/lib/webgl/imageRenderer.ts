import { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { Image2D } from "$lib/webgl/image2D";
import type { AbstractImage } from "./abstractImage";
import type { RenderTarget } from "./types";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import fs_renderImage2D from './glsl/fs_render_image2D.frag';
import fs_renderLuminance from './glsl/fs_render_luminance.frag';
import fs_renderImage3D from './glsl/fs_render_image3D.frag';

export interface ImageRenderer {
    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget): void;
}

export class BaseImageRenderer implements ImageRenderer {

    private readonly shaderBase: TextureShaderProgram;
    private readonly shaderLuminance: TextureShaderProgram;
    private readonly shader3D: TextureShaderProgram;

    constructor(private readonly image: AbstractImage) {
        const { webgl } = image;
        this.shaderBase = new TextureShaderProgram(webgl, fs_renderImage2D);
        this.shaderLuminance = new TextureShaderProgram(webgl, fs_renderLuminance);
        this.shader3D = new TextureShaderProgram(webgl, fs_renderImage3D);
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const { image } = viewerContext;

        const uniforms = getBaseUniforms(viewerContext);
        // console.log(uniforms);
        if (image.is3D) {
            this.shader3D.pass(renderTarget, uniforms);
            return;
        }
        const { renderMode } = viewerContext;

        // image stores different textures for different render modes
        uniforms.u_image = (image as Image2D).selectTexture(renderMode);

        if (renderMode == 'Luminance' || renderMode == 'Red' || renderMode == 'Green' || renderMode == 'Blue') {
            // luminance, red, green, blue are not stored in a separate texture, but calculated in the fragment shader
            uniforms.u_channel = {
                'R': 0,
                'G': 1,
                'B': 2,
                'L': -1,
            }[renderMode[0]];
            this.shaderLuminance.pass(renderTarget, uniforms);
        } else {
            this.shaderBase.pass(renderTarget, uniforms);
        }
    }

}

export function getBaseUniforms(viewerContext: ViewerContext): any {
    const { webglTransform, image, index, windowLevel } = viewerContext;

    return {
        u_index: index,
        u_image: image.texture,
        u_image_size: [image.width, image.height, image.depth],
        u_transform: webglTransform.asUniform,
        u_window_level: [windowLevel.min, windowLevel.max]
    };
}
