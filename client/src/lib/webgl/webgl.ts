import { CFImageProcessing } from '$lib/image-processing/CFImageProcessing';
import { ProgramInfo } from './programInfo';
import { Shaders } from './shaders';
import type { RenderBounds } from './types';

export class WebGL {

    canvas: HTMLCanvasElement;
    gl: WebGL2RenderingContext;

    shaders: Shaders;
    cfImageProcessing: CFImageProcessing;

    constructor(canvas: HTMLCanvasElement) {

        this.canvas = canvas;
        const gl = this.canvas.getContext('webgl2', {
            preserveDrawingBuffer: true,
            premultipliedAlpha: false
        })!;
        this.gl = gl;
        gl.enable(gl.SCISSOR_TEST);
        const ext0 = gl.getExtension('OES_texture_float_linear');
        const ext1 = gl.getExtension('EXT_color_buffer_float');

        this.shaders = new Shaders(this);
        this.cfImageProcessing = new CFImageProcessing(this);
    }

    clear(renderBounds: RenderBounds) {
        const gl = this.gl;
        const { left, bottom, width, height } = renderBounds;
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        gl.viewport(left, bottom, width, height);
        gl.scissor(left, bottom, width, height);
        gl.clearColor(0, 0, 0, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
    }


    async loadProgramInfo(vertexPath: URL, fragmentPath: URL): Promise<ProgramInfo> {
        const vertexSource = await loadShader(vertexPath);
        const fragmentSource = await loadShader(fragmentPath);
        return this.createProgramInfo(vertexSource, fragmentSource);
    }

    createProgramInfo(vertexSource: string, fragmentSource: string): ProgramInfo {
        const gl = this.gl;
        const vs = this.compileShader(vertexSource, gl.VERTEX_SHADER);
        const fs = this.compileShader(fragmentSource, gl.FRAGMENT_SHADER);

        return new ProgramInfo(this.gl, vs, fs);
    }

    compileShader(shaderSource: string, shaderType: number): WebGLShader {
        const gl = this.gl;
        const shader = gl.createShader(shaderType);
        if (!shader) {
            throw new Error('Failed to create shader');
        }
        gl.shaderSource(shader, shaderSource);
        gl.compileShader(shader);
        return shader;
    }
}

async function loadShader(src: URL): Promise<string> {
    const resp = await fetch(src);
    return resp.text();
}