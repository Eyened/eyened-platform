import { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { Image2D } from "$lib/webgl/image2D";
import type { WebGL } from "./webgl";
import type { RenderTarget } from "./types";
import type { Registration } from "$lib/registration/registration";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import fs_redblue from './multiImageFragment/redblue.frag';
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";


export class MultiImageRenderer implements ImageRenderer {
    // private readonly shaderCursor: TextureShaderProgram;
    // private readonly shaderSplit: TextureShaderProgram;
    // private readonly shaderBlend: TextureShaderProgram;
    private shaderRedBlue: TextureShaderProgram;
    // private readonly shaderSeries: TextureShaderProgram;
    private readonly webgl: WebGL;
    private secondary: Image2D;
    public blend: number = 0.5;

    constructor(private readonly image: Image2D, private readonly registration: Registration) {
        const { webgl } = image;
        this.webgl = webgl;
        const fs_base = fs_redblue.replace(`// @insert mapping`, `vec2 mapping(vec2 uv) { return uv; }`);
        this.shaderRedBlue = new TextureShaderProgram(webgl, fs_base);
        this.secondary = image;
        // this.shaderCursor = new TextureShaderProgram(webgl, fragmentCursor);
        // this.shaderSplit = new TextureShaderProgram(webgl, fragmentSplit);
        // this.shaderBlend = new TextureShaderProgram(webgl, fragmentBlend);
        // this.shaderSeries = new TextureShaderProgram(webgl, fragmentSeries);
    }


    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const uniforms = getBaseUniforms(viewerContext);
        uniforms.u_blend = this.blend;
        uniforms.u_secondary = this.secondary.texture;
        uniforms.u_size_primary = [this.image.width, this.image.height];
        uniforms.u_size_secondary = [this.secondary.width, this.secondary.height];

        this.webgl.clear(renderTarget);
        this.shaderRedBlue.pass(renderTarget, uniforms);
    }

    setImage(image: Image2D) {
        this.secondary = image;
        const item = this.registration.getRegistrationItem(this.image.image_id, this.secondary.image_id);
        if (item && item.glslMapping) {
            const fs_updated = fs_redblue.replace(`// @insert mapping`, item.glslMapping);
            this.shaderRedBlue = new TextureShaderProgram(this.webgl, fs_updated);
        }
    }

}