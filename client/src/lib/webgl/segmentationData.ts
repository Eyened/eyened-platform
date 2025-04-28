import type { PixelShaderProgram } from "./FragmentShaderProgram";
import type { AbstractImage } from "./abstractImage";
type TypedArray = Int8Array | Uint8Array | Uint8ClampedArray | Int16Array | Uint16Array | Int32Array | Uint32Array | Float32Array | Float64Array;

export interface SegmentationData {
    getTexture(scanNr: number): WebGLTexture;
    setBscan(scanNr: number, data: TypedArray): void;
    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement): void;
    readBscanFromGPU(scanNr: number): TypedArray;
    getBscan(scanNr: number): TypedArray;
    getVoxel(x: number, y: number, z: number): number;
    dispose(): void;
    passShader(scanNr: number, shader: PixelShaderProgram, uniforms: any): void;
}

class TextureData3D<T extends TypedArray> implements SegmentationData {

    protected framebuffer: WebGLFramebuffer;
    texture: WebGLTexture;

    constructor(readonly image: AbstractImage,
        readonly internalFormat: number, //webgl internal format (R8UI, R16UI, R8)
        readonly format: number, //webgl format (RED, RED_INTEGER)
        readonly type: number, //webgl type (UNSIGNED_BYTE, UNSIGNED_SHORT) 
        readonly data: T) {

        const gl = image.webgl.gl;
        this.texture = this.initTexture();
        this.framebuffer = gl.createFramebuffer()!;
    }

    /**
     * 
     * @param scanNr 
     * @returns Returns a 3D texture, regardless of the scanNr
     */
    getTexture(scanNr: number): WebGLTexture {
        return this.texture;
    }

    /**
     * Updates both gpu and cpu data
     * @param data 
     */
    setVolume(data: T) {
        const { webgl: { gl }, width, height, depth } = this.image;
        gl.bindTexture(gl.TEXTURE_3D, this.texture);
        //target, level, internalformat, width, height, depth, border, format, type, pixels
        gl.texImage3D(gl.TEXTURE_3D, 0, this.internalFormat, width, height, depth, 0, this.format, this.type, data);
        this.data.set(data);
    }

    /**
     * Updates both gpu and cpu data
     * @param scanNr 
     * @param data 
     */
    setBscan(scanNr: number, data: T) {
        const { webgl: { gl }, width, height } = this.image;
        gl.bindTexture(gl.TEXTURE_3D, this.texture);
        //target, level, xoffset, yoffset, zoffset, width, height, depth, format, type, pixels
        gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, scanNr, width, height, 1, this.format, this.type, data);
        this.data.set(data, scanNr * width * height);
    }

    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement) {
        throw new Error('Method not implemented.');
    }

    /**
     * reads the data from the gpu
     * @param scanNr 
     */
    readBscanFromGPU(scanNr: number) {
        const { webgl: { gl }, width, height } = this.image;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.framebufferTextureLayer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, this.texture, 0, scanNr);
        const data = readDataFromFrameBuffer(gl, this.internalFormat, width, height);
        this.data.set(data, scanNr * width * height);
        return data;
    }

    /**
     * returns the cpu data for this bscan (subarray of the 3D data)
     * Note: this is not a copy, but a view of the data
     * @param scanNr 
     */
    getBscan(scanNr: number): T {
        const { width, height } = this.image;
        return this.data.subarray(scanNr * width * height, (scanNr + 1) * width * height);
    }

    getVoxel(x: number, y: number, z: number): number {
        const { width, height } = this.image;
        const i = x + y * width + z * width * height;
        return this.data[i];
    }

    dispose() {
        const { webgl: { gl } } = this.image;
        gl.deleteTexture(this.texture);
        gl.deleteFramebuffer(this.framebuffer);
    }

    initTexture(): WebGLTexture {
        const { webgl: { gl }, width, height, depth } = this.image;
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_3D, texture);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);
        gl.texImage3D(gl.TEXTURE_3D, 0, this.internalFormat, width, height, depth, 0, this.format, this.type, null);
        return texture;
    }

    passShader(scanNr: number, shader: PixelShaderProgram, uniforms: any) {
        // Note: not implemented currently
        // Implementation would be similar to TextureData2DArray
        // Except that we would probably write to the layer directly rather than to another buffer
        // Using: gl.framebufferTextureLayer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, this.texture, 0, scanNr);
        // However, then it would not be possible to use the same texture for reading
        throw new Error('Method not implemented.');
    }

}

class TextureData2DArray implements SegmentationData {
    textures: WebGLTexture[];
    framebuffer: WebGLFramebuffer;
    format: number;
    type: number;
    internalFormat: number;
    data: Uint8Array;
    nChannels: number;
    constructor(
        readonly image: AbstractImage,
        readonly textureFormat: 'R8' | 'R8UI' | 'RG8UI',
    ) {
        const { webgl: { gl }, width, height, depth } = image;
        this.type = gl.UNSIGNED_BYTE;
        if (textureFormat === 'R8') {
            this.format = gl.RED;
            this.internalFormat = gl.R8;
            this.nChannels = 1;
        } else if (textureFormat === 'R8UI') {
            this.format = gl.RED_INTEGER;
            this.internalFormat = gl.R8UI;
            this.nChannels = 1;
        } else if (textureFormat === 'RG8UI') {
            this.format = gl.RG_INTEGER;
            this.internalFormat = gl.RG8UI;
            this.nChannels = 2;
        } else {
            //TODO: Add other formats
            throw new Error(`Unsupported texture format: ${textureFormat}`);
        }
        this.data = new Uint8Array(width * height * depth * this.nChannels);
        this.textures = Array.from({ length: depth }, () => this.initTexture());
        this.framebuffer = gl.createFramebuffer()!;
    }

    dispose() {
        const { webgl: { gl } } = this.image;
        this.textures.forEach(texture => gl.deleteTexture(texture));
    }


    getVoxel(x: number, y: number, z: number): number {
        const { width, height } = this.image;
        const i = x + y * width + z * width * height;
        return this.data[i];
    }

    initTexture(): WebGLTexture {

        const { webgl: { gl }, width, height } = this.image;
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, texture);

        // Linear filtering for non-integer formats, nearest for integer formats
        const filter = (this.textureFormat.indexOf('I') == -1) ? gl.LINEAR : gl.NEAREST;
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, width, height, 0, this.format, this.type, null);
        gl.bindTexture(gl.TEXTURE_2D, null);

        return texture;
    }

    getTexture(scanNr: number): WebGLTexture {
        return this.textures[scanNr];
    }

    setBscan(scanNr: number, data: Uint8Array) {
        const { webgl: { gl }, width, height } = this.image;

        // update gpu data
        gl.bindTexture(gl.TEXTURE_2D, this.textures[scanNr]);
        gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, width, height, 0, this.format, this.type, data);
        gl.bindTexture(gl.TEXTURE_2D, null);

        // update cpu data
        this.data.set(data, scanNr * width * height * this.nChannels);
    }

    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement) {
        const { webgl: { gl }, width, height } = this.image;
        gl.bindTexture(gl.TEXTURE_2D, this.textures[scanNr]);
        gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, width, height, 0, this.format, this.type, canvas);
        gl.bindTexture(gl.TEXTURE_2D, null);
        this.readBscanFromGPU(scanNr);
    }

    readBscanFromGPU(scanNr: number): TypedArray {
        const { webgl: { gl }, width, height } = this.image;

        const texture = this.textures[scanNr];
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
        const data = readDataFromFrameBuffer(gl, this.internalFormat, width, height);

        // update cpu data
        this.data.set(data, scanNr * width * height * this.nChannels);
        return data;
    }

    getBscan(scanNr: number): Uint8Array {
        const { width, height } = this.image;
        const n = this.nChannels * width * height;
        return this.data.subarray(scanNr * n, (scanNr + 1) * n);
    }


    passShader(scanNr: number, shader: PixelShaderProgram, uniforms: any) {
        const { webgl: { gl }, width, height } = this.image;

        // draw to the buffer
        const buffer = this.image.getSwapBuffer(this.internalFormat, () => this.initTexture());
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);

        // currently only one output (gl.COLOR_ATTACHMENT0)
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, buffer, 0);
        const renderTarget = {
            framebuffer: this.framebuffer,
            width, height, left: 0, bottom: 0,
            attachments: [gl.COLOR_ATTACHMENT0]
        };

        // execute the shader
        shader.pass(renderTarget, uniforms);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        // swap the buffers
        const current = this.textures[scanNr];
        this.textures[scanNr] = buffer;
        this.image.setSwapBuffer(this.internalFormat, current);

        // sync the cpu data
        this.readBscanFromGPU(scanNr);
    }
}

export class MulticlassData extends TextureData3D<Uint8Array> {
    constructor(image: AbstractImage) {
        const gl = image.webgl.gl;
        const data = new Uint8Array(image.width * image.height * image.depth);
        super(image, gl.R8UI, gl.RED_INTEGER, gl.UNSIGNED_BYTE, data);
    }
}

export class MultilabelData extends TextureData3D<Uint16Array> {
    constructor(image: AbstractImage) {
        const gl = image.webgl.gl;
        const data = new Uint16Array(image.width * image.height * image.depth);
        super(image, gl.R16UI, gl.RED_INTEGER, gl.UNSIGNED_SHORT, data);
    }
}

export class ProbabilityData extends TextureData2DArray {
    constructor(image: AbstractImage) {
        super(image, 'R8');
    }
}

export class SharedDataRG extends TextureData2DArray {
    public readonly size = 8;
    id: number;
    static _id = 0;
    constructor(image: AbstractImage) {
        super(image, 'RG8UI');
        this.id = SharedDataRG._id++;
    }

}

/**
 * Reads from the current framebuffer
 * 
 * @param gl 
 * @param internalFormat 
 * @param width 
 * @param height 
 * @returns 
 */
function readDataFromFrameBuffer(gl: WebGL2RenderingContext, internalFormat: number, width: number, height: number): TypedArray {
    // NOTE: We can only read RGBA_INTEGER, UNSIGNED_INTEGER for UI formats 
    // or RGBA, UNSIGNED_BYTE for non-UI formats
    // see: https://webgl2fundamentals.org/webgl/lessons/webgl-readpixels.html
    let pixels;
    switch (internalFormat) {
        case gl.R8UI:
        case gl.RG8UI:
        case gl.R16UI:
            pixels = new Uint32Array(width * height * 4);
            gl.readPixels(0, 0, width, height, gl.RGBA_INTEGER, gl.UNSIGNED_INT, pixels);
            break;
        case gl.R8:
            pixels = new Uint8Array(width * height * 4);
            gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            break;
        default:
            // Add other cases above
            throw new Error(`Unsupported internal format: ${internalFormat}`);
    }
    // Now convert the pixels to the correct format
    let data;
    let nChannels = 1;
    switch (internalFormat) {
        case gl.R8:
        case gl.R8UI:
            data = new Uint8Array(width * height);
            break;
        case gl.R16UI:
            data = new Uint16Array(width * height);
            break;
        case gl.RG8UI:
            data = new Uint8Array(width * height * 2);
            nChannels = 2;
            break;
        default:
            // Add other cases above
            throw new Error(`Unsupported internal format: ${internalFormat}`);
    }
    for (let i = 0; i < width * height; i++) {
        for (let j = 0; j < nChannels; j++) {
            data[i * nChannels + j] = pixels[i * 4 + j];
        }
    }
    return data;
}

export function Uint8ArrayToCanvasGray(data: Uint8Array, ctx: CanvasRenderingContext2D) {
    const { width, height } = ctx.canvas;

    const imageData = ctx.getImageData(0, 0, width, height);
    const dataOut = imageData.data;
    for (let i = 0; i < width * height; i++) {
        const value = data[i];
        dataOut[i * 4] = value;
        dataOut[i * 4 + 1] = value;
        dataOut[i * 4 + 2] = value;
        dataOut[i * 4 + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
}

/**
 * splits the 16 bit data into 8 bit red and 8 bit green
 * @param data 
 * @param ctx 
 */
export function Uint16ArrayToCanvas(data: Uint16Array, ctx: CanvasRenderingContext2D) {
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const dataOut = imageData.data;
    for (let i = 0; i < width * height; i++) {
        const value = data[i];
        dataOut[4 * i] = value & 0xff;
        dataOut[4 * i + 1] = value >> 8;
        dataOut[4 * i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
}



export function CanvasToUint8Array(canvas: HTMLCanvasElement): Uint8Array {
    const ctx = canvas.getContext('2d')!;
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = new Uint8Array(width * height);
    for (let i = 0; i < width * height; i++) {
        data[i] = imageData.data[4 * i];
    }
    return data;
}

/**
 * reads the red and green channel of the canvas and combines them into a 16 bit array
 * @param canvas 
 */
export function CanvasToUint16Array(canvas: HTMLCanvasElement): Uint16Array {
    const ctx = canvas.getContext('2d')!;
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = new Uint16Array(width * height);
    for (let i = 0; i < width * height; i++) {
        data[i] = imageData.data[4 * i] + (imageData.data[4 * i + 1] << 8);
    }
    return data;
}