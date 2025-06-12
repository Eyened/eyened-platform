import type { DataRepresentation } from "$lib/datamodel/annotationType";
import type { PixelShaderProgram } from "./FragmentShaderProgram";
import type { AbstractImage } from "./abstractImage";
type TypedArray = Int8Array | Uint8Array | Uint8ClampedArray | Int16Array | Uint16Array | Int32Array | Uint32Array | Float32Array | Float64Array;

export interface SegmentationData {
    getTexture(scanNr: number): WebGLTexture;
    setBscan(scanNr: number, data: TypedArray): void;
    clearBscan(scanNr: number): void;
    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement): void;
    readBscanFromGPU(scanNr: number): TypedArray;
    getBscan(scanNr: number): TypedArray;
    getVoxel(x: number, y: number, z: number): number;
    dispose(): void;
    passShader(scanNr: number, shader: PixelShaderProgram, uniforms: any): void;
}

class TextureData3D implements SegmentationData {

    protected framebuffer: WebGLFramebuffer;
    texture: WebGLTexture;

    constructor(readonly gl: WebGL2RenderingContext,
        readonly width: number,
        readonly height: number,
        readonly depth: number,
        readonly internalFormat: number, //webgl internal format (R8UI, R16UI, R8)
        readonly format: number, //webgl format (RED, RED_INTEGER)
        readonly type: number, //webgl type (UNSIGNED_BYTE, UNSIGNED_SHORT) 
        readonly data: Uint8Array | Uint16Array | Uint32Array) {

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
    setVolume(data: Uint8Array | Uint16Array | Uint32Array) {
        this.gl.bindTexture(this.gl.TEXTURE_3D, this.texture);
        //target, level, internalformat, width, height, depth, border, format, type, pixels
        this.gl.texImage3D(this.gl.TEXTURE_3D, 0, this.internalFormat, this.width, this.height, this.depth, 0, this.format, this.type, data);
        this.data.set(data);
    }

    /**
     * Updates both gpu and cpu data
     * @param scanNr 
     * @param data 
     */
    setBscan(scanNr: number, data: Uint8Array | Uint16Array | Uint32Array) {
        this.gl.bindTexture(this.gl.TEXTURE_3D, this.texture);
        //target, level, xoffset, yoffset, zoffset, width, height, depth, format, type, pixels
        this.gl.texSubImage3D(this.gl.TEXTURE_3D, 0, 0, 0, scanNr, this.width, this.height, 1, this.format, this.type, data);
        this.data.set(data, scanNr * this.width * this.height);
    }

    clearBscan(scanNr: number) {
        this.gl.bindTexture(this.gl.TEXTURE_3D, this.texture);
        this.gl.texSubImage3D(this.gl.TEXTURE_3D, 0, 0, 0, scanNr, this.width, this.height, 1, this.format, this.type, null);
        this.data.fill(0, scanNr * this.width * this.height, (scanNr + 1) * this.width * this.height);
    }

    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement) {
        throw new Error('Method not implemented.');
    }

    /**
     * reads the data from the gpu
     * @param scanNr 
     */
    readBscanFromGPU(scanNr: number) {
        this.gl.bindFramebuffer(this.gl.FRAMEBUFFER, this.framebuffer);
        this.gl.framebufferTextureLayer(this.gl.FRAMEBUFFER, this.gl.COLOR_ATTACHMENT0, this.texture, 0, scanNr);
        const data = readDataFromFrameBuffer(this.gl, this.internalFormat, this.width, this.height);
        this.data.set(data, scanNr * this.width * this.height);
        return data;
    }

    /**
     * returns the cpu data for this bscan (subarray of the 3D data)
     * Note: this is not a copy, but a view of the data
     * @param scanNr 
     */
    getBscan(scanNr: number): Uint8Array | Uint16Array | Uint32Array {
        return this.data.subarray(scanNr * this.width * this.height, (scanNr + 1) * this.width * this.height);
    }

    getVoxel(x: number, y: number, z: number): number {
        const i = x + y * this.width + z * this.width * this.height;
        return this.data[i];
    }

    dispose() {
        this.gl.deleteTexture(this.texture);
        this.gl.deleteFramebuffer(this.framebuffer);
    }

    initTexture(): WebGLTexture {
        const texture = this.gl.createTexture()!;
        const gl = this.gl;

        // Check max texture dimensions
        const maxSize = gl.getParameter(gl.MAX_3D_TEXTURE_SIZE);
        if (this.width > maxSize || this.height > maxSize || this.depth > maxSize) {
            throw new Error(`Texture dimensions (${this.width}x${this.height}x${this.depth}) exceed maximum supported size of ${maxSize}x${maxSize}x${maxSize}`);
        }

        gl.bindTexture(gl.TEXTURE_3D, texture);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);
        gl.texImage3D(gl.TEXTURE_3D, 0, this.internalFormat, this.width, this.height, this.depth, 0, this.format, this.type, null);
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
    data: Uint8Array | Uint16Array | Uint32Array;
    nChannels: number;
    gl: WebGL2RenderingContext;

    constructor(
        readonly image: AbstractImage,
        readonly width: number,
        readonly height: number,
        readonly depth: number,
        readonly textureFormat: 'R8' | 'R8UI' | 'R16UI' | 'R32UI'  
    ) {
        const gl = image.webgl.gl;
        this.gl = gl;
        if (textureFormat === 'R8') {
            this.type = gl.UNSIGNED_BYTE;
            this.format = gl.RED;
            this.internalFormat = gl.R8;
            this.nChannels = 1;
            this.data = new Uint8Array(width * height * depth * this.nChannels);
        } else if (textureFormat === 'R8UI') {
            this.type = gl.UNSIGNED_BYTE;
            this.format = gl.RED_INTEGER;
            this.internalFormat = gl.R8UI;
            this.nChannels = 1;
            this.data = new Uint8Array(width * height * depth * this.nChannels);
        } else if (textureFormat === 'R16UI') {
            this.type = gl.UNSIGNED_SHORT;
            this.format = gl.RED_INTEGER;
            this.internalFormat = gl.R16UI;
            this.nChannels = 1;
            this.data = new Uint16Array(width * height * depth * this.nChannels);
        } else if (textureFormat === 'R32UI') {
            this.type = gl.UNSIGNED_INT;
            this.format = gl.RED_INTEGER;
            this.internalFormat = gl.R32UI;
            this.nChannels = 1;
            this.data = new Uint32Array(width * height * depth * this.nChannels);
        } else {
            throw new Error(`Unsupported texture format: ${textureFormat}`);
        }
        this.textures = Array.from({ length: depth }, () => this.initTexture());
        this.framebuffer = gl.createFramebuffer()!;
    }

    dispose() {
        this.textures.forEach(texture => this.gl.deleteTexture(texture));
    }


    getVoxel(x: number, y: number, z: number): number {
        const i = x + y * this.width + z * this.width * this.height;
        return this.data[i];
    }

    initTexture(): WebGLTexture {

        const texture = this.gl.createTexture()!;
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        const gl = this.gl;
        // Linear filtering for non-integer formats, nearest for integer formats
        const filter = (this.textureFormat.indexOf('I') == -1) ? gl.LINEAR : gl.NEAREST;
        this.gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, this.width, this.height, 0, this.format, this.type, null);
        gl.bindTexture(gl.TEXTURE_2D, null);

        return texture;
    }

    getTexture(scanNr: number): WebGLTexture {
        return this.textures[scanNr];
    }

    setBscan(scanNr: number, data: Uint8Array | Uint16Array | Uint32Array) {
        // update gpu data
        const gl = this.gl;
        gl.bindTexture(this.gl.TEXTURE_2D, this.textures[scanNr]);
        gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, this.width, this.height, 0, this.format, this.type, data);
        gl.bindTexture(gl.TEXTURE_2D, null);

        // update cpu data
        this.data.set(data, scanNr * this.width * this.height * this.nChannels);
    }

    clearBscan(scanNr: number) {
        this.gl.bindTexture(this.gl.TEXTURE_2D, this.textures[scanNr]);
        this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.internalFormat, this.width, this.height, 0, this.format, this.type, null);
        this.gl.bindTexture(this.gl.TEXTURE_2D, null);
        this.data.fill(0, scanNr * this.width * this.height * this.nChannels, (scanNr + 1) * this.width * this.height * this.nChannels);
    }

    setBscanCanvas(scanNr: number, canvas: HTMLCanvasElement) {
        const gl = this.gl;
        gl.bindTexture(this.gl.TEXTURE_2D, this.textures[scanNr]);
        gl.texImage2D(this.gl.TEXTURE_2D, 0, this.internalFormat, this.width, this.height, 0, this.format, this.type, canvas);
        gl.bindTexture(this.gl.TEXTURE_2D, null);
        this.readBscanFromGPU(scanNr);
    }

    readBscanFromGPU(scanNr: number): TypedArray {
        const gl = this.gl;
        const texture = this.textures[scanNr];
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
        const data = readDataFromFrameBuffer(gl, this.internalFormat, this.width, this.height);

        // update cpu data
        this.data.set(data, scanNr * this.width * this.height * this.nChannels);
        return data;
    }

    getBscan(scanNr: number): Uint8Array | Uint16Array | Uint32Array {
        const n = this.nChannels * this.width * this.height;
        return this.data.subarray(scanNr * n, (scanNr + 1) * n);
    }


    passShader(scanNr: number, shader: PixelShaderProgram, uniforms: any) {
        const gl = this.gl;

        // draw to the buffer
        const buffer = this.image.getSwapBuffer(this.internalFormat, () => this.initTexture());
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);

        // currently only one output (gl.COLOR_ATTACHMENT0)
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, buffer, 0);
        const renderTarget = {
            framebuffer: this.framebuffer,
            width: this.width,
            height: this.height,
            left: 0,
            bottom: 0,
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

export class MulticlassData extends TextureData3D {
    constructor(gl: WebGL2RenderingContext, width: number, height: number, depth: number) {
        const data = new Uint8Array(width * height * depth);
        super(gl, width, height, depth, gl.R8UI, gl.RED_INTEGER, gl.UNSIGNED_BYTE, data);
    }
}

export class MultilabelData3D extends TextureData3D {
    constructor(gl: WebGL2RenderingContext, width: number, height: number, depth: number, numLabels: number) {
        let data;
        let format;
        let type;
        if (numLabels < 8) {
            data = new Uint8Array(width * height * depth);
            format = gl.R8UI;
            type = gl.UNSIGNED_BYTE;
        } else if (numLabels < 16) {
            data = new Uint16Array(width * height * depth);
            format = gl.R16UI;
            type = gl.UNSIGNED_SHORT;
        } else if (numLabels < 32) {
            data = new Uint32Array(width * height * depth);
            format = gl.R32UI;
            type = gl.UNSIGNED_INT;
        } else {
            throw new Error(`Unsupported number of labels: ${numLabels}`);
        }
        console.log('MultilabelData', width, height, depth, numLabels, format, type);
        super(gl, width, height, depth, format, gl.RED_INTEGER, type, data);
    }
}
export class MultilabelData2D extends TextureData2DArray {
    constructor(image: AbstractImage, width: number, height: number, numLabels: number) {
        let dataformat: 'R8UI' | 'R16UI' | 'R32UI';
        if (numLabels < 8) {
            dataformat = 'R8UI';
        } else if (numLabels < 16) {
            dataformat = 'R16UI';
        } else if (numLabels < 32) {
            dataformat = 'R32UI';
        } else {
            throw new Error(`Unsupported number of labels: ${numLabels}`);
        }
        super(image, width, height, 1, dataformat);
    }
}

export class ProbabilityData extends TextureData2DArray {
    constructor(image: AbstractImage, width: number, height: number, depth: number) {
        super(image, width, height, depth, 'R8');
    }
}

export class SharedData extends TextureData2DArray {
    public readonly size = 8;
    id: number;
    static _id = 0;
    constructor(image: AbstractImage, width: number, height: number, depth: number) {
        super(image, width, height, depth, 'R8UI');
        this.id = SharedData._id++;
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


export function Uint8ArrayToCanvas(data: Uint8Array, ctx: CanvasRenderingContext2D,
    dataRepresentation: DataRepresentation, threshold: number = 0.5) {
    if (dataRepresentation === 'FLOAT') {
        return Uint8ArrayToCanvasGray(data, ctx);
    }
    const isRGMask = dataRepresentation === 'RG_MASK';
    const { width, height } = ctx.canvas;
    const th = threshold * 255;
    const imageData = ctx.getImageData(0, 0, width, height);
    const dataOut = imageData.data;
    for (let i = 0; i < width * height; i++) {
        const value = data[i];
        if (value > th) {
            dataOut[i * 4] = 255; // R=255 for annotation
            if (isRGMask) {
                // do not set G or B for RG_MASK
            } else {
                dataOut[i * 4 + 1] = 255;
                dataOut[i * 4 + 2] = 255;
            }
        }
        dataOut[i * 4 + 3] = 255; // alpha = 255
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

/**
 * splits the 32 bit data into 8 bit red, green, blue and alpha
 * @param data 
 * @param ctx 
 */
export function Uint32ArrayToCanvas(data: Uint32Array, ctx: CanvasRenderingContext2D) {
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const dataOut = imageData.data;
    for (let i = 0; i < width * height; i++) {
        const value = data[i];
        dataOut[4 * i] = value & 0xff;
        dataOut[4 * i + 1] = (value >> 8) & 0xff;
        dataOut[4 * i + 2] = (value >> 16) & 0xff;
        dataOut[4 * i + 3] = (value >> 24) & 0xff;
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

/**
 * reads the red, green and blue channel of the canvas and combines them into a 32 bit array
 * @param canvas 
 */
export function CanvasToUint32Array(canvas: HTMLCanvasElement): Uint32Array {
    const ctx = canvas.getContext('2d')!;
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = new Uint32Array(width * height);
    for (let i = 0; i < width * height; i++) {
        data[i] = (
            (imageData.data[4 * i]) +
            (imageData.data[4 * i + 1] << 8) +
            (imageData.data[4 * i + 2] << 16) +
            (imageData.data[4 * i + 3] << 24)
        );
    }
    return data;
}