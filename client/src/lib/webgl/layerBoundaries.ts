import type { AbstractImage } from "./abstractImage";

export class LayerBoundaries {

    n_layers = 13;
    texture: WebGLTexture;
    constructor(readonly image: AbstractImage, readonly layersTexture: WebGLTexture) {
        this.texture = this.initTexture();
        this.calculateBoundaries();
    }

    initTexture(): WebGLTexture {
        // texture size: width x depth x n_layers (e.g. 512 x 128 x 12)
        const { webgl, width, depth } = this.image;
        const { gl } = webgl;

        // 16 bit unsigned integer for boundary value in range 0-885
        // Red channel: top boundary
        // Green channel: bottom boundary
        const internalFormat = gl.RG16UI;

        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_3D, texture);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);

        gl.texImage3D(gl.TEXTURE_3D, 0, internalFormat, width, depth, this.n_layers, 0, gl.RG_INTEGER, gl.UNSIGNED_SHORT, null);
        return texture;
    }

    calculateBoundaries() {

        const { webgl, width, height, depth } = this.image;
        const { gl } = webgl;
        const shader = webgl.shaders.calculateBoundaries;

        const framebuffer = webgl.gl.createFramebuffer()!;
        gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
        for (let i = 0; i < this.n_layers; i++) {
            const renderTarget = {
                width: width,
                height: depth,
                left: 0,
                bottom: 0,
                framebuffer
            }
            gl.framebufferTextureLayer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, this.texture, 0, i);
            const uniforms = {
                u_layers: this.layersTexture,
                u_depth: height,
                u_boundary: i + 1
            };
            shader.pass(renderTarget, uniforms);
        }

    }



}