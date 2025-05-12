import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";

export type TextureDataFormat = 'RG32UI' | 'RG16UI' | 'R16UI' | 'R8' | 'R8UI' | 'RGBA' | 'RGBA_FLOAT' | 'R32UI' | 'RG8';

export class RenderTexture {

    public readonly framebuffer: WebGLFramebuffer;
    public readonly texture: WebGLTexture;

    constructor(
        private readonly webgl: WebGL,
        public readonly width: number,
        public readonly height: number,
        public readonly format: TextureDataFormat,
        source: HTMLCanvasElement | HTMLImageElement | Uint8Array | null
    ) {
        const gl = webgl.gl;
        this.texture = gl.createTexture()!;
        this.framebuffer = gl.createFramebuffer()!;

        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        if (format === 'R8') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, width, height, 0, gl.RED, gl.UNSIGNED_BYTE, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        } else if (format === 'RG8'){
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG8, width, height, 0, gl.RG, gl.UNSIGNED_BYTE, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        } else if (format === 'R8UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        } else if (format === 'RG32UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG32UI, width, height, 0, gl.RG_INTEGER, gl.UNSIGNED_INT, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        } else if (format === 'RG16UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG16UI, width, height, 0, gl.RG_INTEGER, gl.UNSIGNED_SHORT, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        } else if (format === 'R16UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R16UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_SHORT, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        } else if (format === 'RGBA') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        } else if (format === 'RGBA_FLOAT') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, width, height, 0, gl.RGBA, gl.FLOAT, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        } else if (format === 'R32UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R32UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_INT, source);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        } else {
            throw new Error(`Unsupported texture type: ${format}`);
        }

        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.bindTexture(gl.TEXTURE_2D, null);

        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.texture, 0);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }

    setDataArray(data: Uint8Array) {
        const gl = this.webgl.gl;
        const { width, height } = this;

        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        if (this.format === 'R8UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, width, height, 0, gl.RED, gl.UNSIGNED_BYTE, data)
        } else if (this.format === 'RG8') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG8, width, height, 0, gl.RG, gl.UNSIGNED_BYTE, data)
        } else if (this.format === 'R8') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, width, height, 0, gl.RED, gl.UNSIGNED_BYTE, data)
        } else if (this.format === 'RGBA') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
        } else {
            // other formats could be added here
            throw new Error(`Unsupported format: ${this.format}`);
        }
        gl.bindTexture(gl.TEXTURE_2D, null);

    }

    setData(canvas: HTMLCanvasElement) {
        const gl = this.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.texture);

        if (this.format === 'RGBA') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
        } else if (this.format === 'R8') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, gl.RED, gl.UNSIGNED_BYTE, canvas);
        } else if (this.format === 'R8UI') {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, gl.RED, gl.UNSIGNED_BYTE, canvas);
        } else {
            throw new Error(`Unsupported format: ${this.format}`);
        }

        gl.bindTexture(gl.TEXTURE_2D, null);
    }

    readData() {
        const readUInts = () => {
            const pixels = new Uint32Array(this.width * this.height * 4);
            gl.readPixels(0, 0, this.width, this.height, gl.RGBA_INTEGER, gl.UNSIGNED_INT, pixels);
            gl.bindFramebuffer(gl.FRAMEBUFFER, null);
            return pixels;
        }
        const readBytes = () => {
            const pixels = new Uint8Array(this.width * this.height * 4);
            gl.readPixels(0, 0, this.width, this.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            gl.bindFramebuffer(gl.FRAMEBUFFER, null);
            return pixels;
        }
        const gl = this.webgl.gl;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        let pixels;
        if (this.format.includes('UI')) {
            pixels = readUInts();
        } else {
            pixels = readBytes();
        }

        let numChannels;
        if (this.format.includes('RGBA')) {
            numChannels = 4;
        } else if (this.format.includes('RGB')) {
            numChannels = 3;
        } else if (this.format.includes('RG')) {
            numChannels = 2;
        } else if (this.format.includes('R')) {
            numChannels = 1;
        } else {
            throw new Error(`Unsupported format: ${this.format}`);
        }
        let result;
        if (this.format.includes('32')) {
            result = new Uint32Array(this.width * this.height * numChannels);
        } else if (this.format.includes('16')) {
            result = new Uint16Array(this.width * this.height * numChannels);
        } else {
            result = new Uint8Array(this.width * this.height * numChannels);
        }
        for (let i = 0; i < this.width * this.height; i++) {
            for (let j = 0; j < numChannels; j++) {
                result[i * numChannels + j] = pixels[i * 4 + j];
            }
        }
        return result;
    }

    getData(ctx: CanvasRenderingContext2D) {
        //assert type === 'RGBA'
        const gl = this.webgl.gl;

        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        const pixels = new Uint8Array(this.width * this.height * 4);
        gl.readPixels(0, 0, this.width, this.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        const imageData = ctx.createImageData(this.width, this.height);
        imageData.data.set(pixels);
        ctx.putImageData(imageData, 0, 0);
    }

    getRenderTarget(): RenderTarget {
        return {
            framebuffer: this.framebuffer,
            width: this.width,
            height: this.height,
            left: 0,
            bottom: 0,
            attachments: [this.webgl.gl.COLOR_ATTACHMENT0]
        };
    }

    dispose() {
        const gl = this.webgl.gl;
        gl.deleteFramebuffer(this.framebuffer);
        gl.deleteTexture(this.texture);
    }
}