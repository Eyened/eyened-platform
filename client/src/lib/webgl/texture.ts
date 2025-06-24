import type { PixelShaderProgram } from "./FragmentShaderProgram";
import type { RenderTarget } from "./types";

export type TypedArray = Int8Array | Uint8Array | Uint8ClampedArray | Int16Array | Uint16Array | Int32Array | Uint32Array | Float32Array | Float64Array;
export type ImageType = HTMLImageElement | HTMLCanvasElement | ImageBitmap;

interface TextureFormat {
    internalFormat: number;
    format: number;
    type: number;
    filtering: number;
}

class SwapTexture {
    constructor(
        public readonly gl: WebGL2RenderingContext,
        public texture: WebGLTexture,
        public readonly framebuffer: WebGLFramebuffer,
        public readonly key: string,
        public readonly textureIO: WebGLTexture
    ) { }

    getTextureForImage(image: ImageType): WebGLTexture {
        // upload canvas to texture
        // reuse the same texture 
        const gl = this.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.textureIO);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        return this.textureIO;
    }

    setTexture(texture: WebGLTexture): void {
        this.texture = texture;
    }
}

function getSwapManager(gl: WebGL2RenderingContext): SwapTextureManager {
    if (!SwapTextureManager.instance) {
        SwapTextureManager.instance = new SwapTextureManager(gl);
    }
    return SwapTextureManager.instance;
}

export function createTexture(gl: WebGL2RenderingContext, format: TextureFormat, width: number, height: number): WebGLTexture {
    const texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texStorage2D(gl.TEXTURE_2D, 1, format.internalFormat, width, height);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, format.filtering);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, format.filtering);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return texture;
}

function createTextureIO(gl: WebGL2RenderingContext, width: number, height: number): WebGLTexture {
    const texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.bindTexture(gl.TEXTURE_2D, null);
    return texture;
}

export function createTextureR8UI(gl: WebGL2RenderingContext, width: number, height: number): WebGLTexture {
    const texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return texture;
}
class SwapTextureManager {
    static instance: SwapTextureManager;
    private swapTextures: Map<string, SwapTexture> = new Map();
    public readonly framebuffer: WebGLFramebuffer;

    constructor(private gl: WebGL2RenderingContext) {
        this.framebuffer = gl.createFramebuffer()!;
    }

    private getTextureKey(format: TextureFormat, width: number, height: number): string {
        return `${format.internalFormat}_${width}_${height}_${format.filtering}`;
    }

    getSwapTexture(format: TextureFormat, width: number, height: number): SwapTexture {
        const key = this.getTextureKey(format, width, height);
        let swap = this.swapTextures.get(key);
        if (!swap) {
            const texture = createTexture(this.gl, format, width, height);
            const textureIO = createTextureIO(this.gl, width, height);
            swap = new SwapTexture(this.gl, texture, this.framebuffer, key, textureIO);
            this.swapTextures.set(key, swap);
        }
        return swap;
    }

}

const INT_FORMAT = {
    format: WebGL2RenderingContext.RED_INTEGER,
    filtering: WebGL2RenderingContext.NEAREST
}
const FLOAT_FORMAT = {
    format: WebGL2RenderingContext.RED,
    type: WebGL2RenderingContext.UNSIGNED_BYTE,
    filtering: WebGL2RenderingContext.LINEAR
}
const TEXTURE_FORMATS: Record<'R8' | 'R8UI' | 'R16UI' | 'R32UI', TextureFormat> = {
    // Used for probability maps
    R8: {
        ...FLOAT_FORMAT,
        internalFormat: WebGL2RenderingContext.R8
    },
    // Used for segmentation maps (8 bit)
    R8UI: {
        ...INT_FORMAT,
        type: WebGL2RenderingContext.UNSIGNED_BYTE,
        internalFormat: WebGL2RenderingContext.R8UI
    },
    // Used for segmentation maps (16 bit)
    R16UI: {
        ...INT_FORMAT,
        type: WebGL2RenderingContext.UNSIGNED_SHORT,
        internalFormat: WebGL2RenderingContext.R16UI
    },
    // Used for segmentation maps (32 bit)
    R32UI: {
        ...INT_FORMAT,
        type: WebGL2RenderingContext.UNSIGNED_INT,
        internalFormat: WebGL2RenderingContext.R32UI
    }
};

export class TextureData {
    private _texture: WebGLTexture | null = null;
    private cpuData: Uint8Array | Uint16Array | Uint32Array | null = null;
    private gpuDirty = false;
    private cpuDirty = false;
    textureFormat: TextureFormat;
    renderTarget: RenderTarget;
    private arrayType: new (length: number) => Uint8Array | Uint16Array | Uint32Array;

    constructor(
        private readonly gl: WebGL2RenderingContext,
        public readonly width: number,
        public readonly height: number,
        private readonly format: keyof typeof TEXTURE_FORMATS
    ) {
        this.textureFormat = TEXTURE_FORMATS[this.format];
        if (this.format === 'R8' || this.format === 'R8UI') {
            this.arrayType = Uint8Array;
        } else if (this.format === 'R16UI') {
            this.arrayType = Uint16Array;
        } else {
            this.arrayType = Uint32Array;
        }
        this.renderTarget = {
            framebuffer: getSwapManager(gl).framebuffer,
            width: this.width,
            height: this.height,
            left: 0,
            bottom: 0,
            attachments: [gl.COLOR_ATTACHMENT0]
        };
    }

    private _getTexture(): WebGLTexture {
        if (!this._texture) {
            this._texture = createTexture(this.gl, this.textureFormat, this.width, this.height);
        }
        return this._texture;
    }

    private _getData(): Uint8Array | Uint16Array | Uint32Array {
        if (!this.cpuData) {
            this.cpuData = new this.arrayType(this.width * this.height);
        }
        return this.cpuData;
    }

    private updateGPU(): void {
        if (this.gpuDirty) {
            const gl = this.gl;
            const { format, type } = this.textureFormat;
            gl.bindTexture(gl.TEXTURE_2D, this._getTexture());
            gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, this.width, this.height, format, type, this._getData());
            this.gpuDirty = false;
        }
    }

    private updateCPU(): void {
        if (this.cpuDirty) {
            const gl = this.gl;
            const { internalFormat } = this.textureFormat;
            const data = this._getData();

            gl.bindFramebuffer(gl.FRAMEBUFFER, this.renderTarget.framebuffer);
            gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this._getTexture(), 0);
            readDataFromFrameBuffer(gl, internalFormat, this.width, this.height, data);
            this.cpuDirty = false;
        }
    }

    get texture(): WebGLTexture {
        this.updateGPU();
        return this._getTexture();
    }

    get data(): Uint8Array | Uint16Array | Uint32Array {
        this.updateCPU();
        return this._getData();
    }

    uploadData(data: Uint8Array | Uint16Array | Uint32Array): void {
        this._getData().set(data);
        this.gpuDirty = true;
        this.cpuDirty = false;
    }

    clearData(): void {
        this._getData().fill(0);
        this.gpuDirty = true;
        this.cpuDirty = false;
    }

    passShader(shader: PixelShaderProgram, uniforms: any): void {
        // sync GPU data with CPU data if needed
        this.updateGPU();
        const gl = this.gl;
        const swap = getSwapManager(gl).getSwapTexture(this.textureFormat, this.width, this.height);

        // Bind the framebuffer and attach the swap texture
        gl.bindFramebuffer(gl.FRAMEBUFFER, swap.framebuffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, swap.texture, 0);

        // Execute the shader (renders to swap texture)
        shader.pass(this.renderTarget, uniforms);


        // Swap textures (swap texture is now the current texture)
        const current = this._texture!;
        this._texture = swap.texture;
        swap.setTexture(current);

        // Mark CPU data as dirty since GPU data has changed
        this.cpuDirty = true;
    }

    markGPUDirty(): void {
        this.gpuDirty = true;
        this.cpuDirty = false;
    }

    getTextureForImage(image: ImageType): WebGLTexture {
        const swap = getSwapManager(this.gl).getSwapTexture(this.textureFormat, this.width, this.height);
        return swap.getTextureForImage(image);
    }
}

export class BinaryMask {
    readonly bitmask: number;
    textureData: TextureData;

    constructor(readonly textureDataAllocation: TextureDataAllocation, readonly index: number) {
        this.textureData = textureDataAllocation.textureData;
        this.bitmask = 1 << index;
    }

    get texture(): WebGLTexture {
        return this.textureData.texture;
    }

    passShader(shader: PixelShaderProgram, uniforms: any): void {
        uniforms.u_bitmask = this.bitmask;
        uniforms.u_current = this.textureData.texture;
        this.textureData.passShader(shader, uniforms);
    }

    clearData(): void {
        const cpuData = this.textureData.data;
        for (let i = 0; i < cpuData.length; i++) {
            cpuData[i] &= ~this.bitmask;
        }
        this.textureData.markGPUDirty();
    }

    getData(): Uint8Array {
        const data = this.textureData.data;
        const result = new Uint8Array(data.length);
        for (let i = 0; i < data.length; i++) {
            if (data[i] & this.bitmask) {
                result[i] = 255;
            } else {
                result[i] = 0;
            }
        }
        return result;
    }

    setData(data: TypedArray): void {
        const cpuData = this.textureData.data;
        for (let i = 0; i < data.length; i++) {
            if (data[i] > 0) {
                cpuData[i] |= this.bitmask;
            } else {
                cpuData[i] &= ~this.bitmask;
            }
        }
        this.textureData.markGPUDirty();
    }

    dispose(): void {
        this.textureDataAllocation.freeMask(this);
    }

    getTextureForImage(image: ImageType): WebGLTexture {
        return this.textureData.getTextureForImage(image);
    }
}

class TextureDataAllocation {
    private masks: (BinaryMask | null)[] = Array(8).fill(null);

    constructor(
        private readonly manager: BinaryMaskManager,
        public readonly textureData: TextureData
    ) { }

    allocateMask(): BinaryMask | null {
        for (let i = 0; i < this.masks.length; i++) {
            if (this.masks[i] === null) {
                const mask = new BinaryMask(this, i);
                this.masks[i] = mask;
                return mask;
            }
        }
        return null;
    }

    freeMask(mask: BinaryMask): void {
        this.masks[mask.index] = null;
        if (this.isEmpty()) {
            this.manager.freeAllocation(this);
        }
    }

    isFull(): boolean {
        return this.masks.every(mask => mask !== null);
    }

    isEmpty(): boolean {
        return this.masks.every(mask => mask === null);
    }
}

export class BinaryMaskManager {
    private allocations: Map<string, TextureDataAllocation[]> = new Map();

    constructor(private readonly gl: WebGL2RenderingContext) { }

    private getKey(width: number, height: number): string {
        return `${width}_${height}`;
    }

    private getAllocations(width: number, height: number): TextureDataAllocation[] {
        const key = this.getKey(width, height);
        return this.allocations.get(key) || [];
    }

    allocateMask(width: number, height: number): BinaryMask {
        const allocations = this.getAllocations(width, height);

        // Try to allocate from existing TextureData instances
        for (const allocation of allocations) {
            const mask = allocation.allocateMask();
            if (mask) {
                return mask;
            }
        }

        // If all TextureData instances are full, create a new one
        const newAllocation = new TextureDataAllocation(this, new TextureData(this.gl, width, height, 'R8UI'));
        const key = this.getKey(width, height);
        this.allocations.set(key, [...allocations, newAllocation]);
        return newAllocation.allocateMask()!;
    }

    /**
     * @internal: should be called by TextureDataAllocation
     * Use BinaryMask.dispose() instead
     */
    freeAllocation(allocation: TextureDataAllocation): void {
        const key = this.getKey(allocation.textureData.width, allocation.textureData.height);
        const allocations = this.allocations.get(key)!;
        const index = allocations.indexOf(allocation);
        if (index !== -1) {
            allocations.splice(index, 1);
            if (allocations.length === 0) {
                this.allocations.delete(key);
            }
        }
    }
}


function readDataFromFrameBuffer(gl: WebGL2RenderingContext, internalFormat: number, width: number, height: number, target: TypedArray) {
    // NOTE: We can only read RGBA_INTEGER, UNSIGNED_INTEGER for UI formats 
    // or RGBA, UNSIGNED_BYTE for non-UI formats
    // see: https://webgl2fundamentals.org/webgl/lessons/webgl-readpixels.html
    let pixels;
    switch (internalFormat) {
        case gl.R8UI:
        case gl.R16UI:
        case gl.R32UI:
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
    switch (internalFormat) {
        case gl.R8:
        case gl.R8UI:
            data = new Uint8Array(width * height);
            break;
        case gl.R16UI:
            data = new Uint16Array(width * height);
            break;
        case gl.R32UI:
            data = new Uint32Array(width * height);
            break;
        default:
            // Add other cases above
            throw new Error(`Unsupported internal format: ${internalFormat}`);
    }
    for (let i = 0; i < width * height; i++) {
        const i_pixel = i * 4;
        target[i] = pixels[i_pixel];
    }
}