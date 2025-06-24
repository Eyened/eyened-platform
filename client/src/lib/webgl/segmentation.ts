import { BlobExtraction } from "$lib/image-processing/connected-component-labelling";
import { colorsFlat } from "$lib/viewer/overlays/colors";
import type { AbstractImage } from "./abstractImage";
import type { Shaders } from "./shaders";
import { createTextureR8UI, TextureData, type BinaryMask, type ImageType, type TypedArray } from "./texture";
import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";

export interface ImportOptions {
    threshold?: number;
    channel?: number;
}

export interface PaintSettings {
    paint?: boolean;
    dilateErode?: boolean;
    questionable?: boolean;
}

export interface Segmentation {
    importImage(image: ImageType, importOptions?: ImportOptions): void;
    exportImage(ctx: CanvasRenderingContext2D): void;
    importData(data: TypedArray): void;
    exportData(): Uint8Array;
    draw(drawing: ImageType, paintSettings: PaintSettings): void;
    clear(): void;
    dispose(): void;
    render(renderTarget: RenderTarget, uniforms: any): void;
}

export class BinarySegmentation implements Segmentation {

    protected _binaryMask: BinaryMask | null = null;
    protected webgl: WebGL;
    protected shaders: Shaders;

    constructor(
        protected readonly image: AbstractImage
    ) {
        this.webgl = this.image.webgl;
        this.shaders = this.webgl.shaders;
    }

    get binaryMask(): BinaryMask {
        if (!this._binaryMask) {
            this._binaryMask = this.webgl.binaryMaskManager.allocateMask(this.image.width, this.image.height);
        }
        return this._binaryMask!;
    }

    /**
     * reads the channel of the canvas and sets the binary mask to the values > threshold     
     * @param canvas the canvas to import from
     * @param threshold in [0,1] (0-255 in the canvas)
     * @param channel the channel to import from (r=0, g=1, b=2, a=3)
     */
    importImage(image: ImageType, importOptions: ImportOptions = { threshold: 0.5, channel: 0 }): void {
        const canvas = new OffscreenCanvas(image.width, image.height);
        const ctx = canvas.getContext('2d')!;
        ctx.drawImage(image, 0, 0);
        const uniforms = {
            u_import: this.binaryMask.getTextureForImage(image),
            u_threshold: importOptions.threshold,
            u_import_channel: importOptions.channel
        };
        this.binaryMask.passShader(this.shaders.import, uniforms);
        this.connectedComponentsValid = false;
    }

    /**
     * exports the binary mask to a canvas (attached to the context)
     * writes white (255,255,255,255) for values > 0, black (0,0,0,255) for background (values == 0)
     * @param ctx the context to export to
     */
    exportImage(ctx: CanvasRenderingContext2D): void {
        const data = this.binaryMask.getData();
        const { width, height } = this.image;

        const imageData = ctx.getImageData(0, 0, width, height);
        const dataOut = imageData.data;
        for (let i = 0; i < width * height; i++) {
            const dataOutIndex = 4 * i;
            if (data[i] > 0) {
                dataOut[dataOutIndex] = 255;
                dataOut[dataOutIndex + 1] = 255;
                dataOut[dataOutIndex + 2] = 255;
            }
            dataOut[dataOutIndex + 3] = 255;
        }
        ctx.putImageData(imageData, 0, 0);
    }

    /**
     * imports the binary mask from a Uint8Array
     * @param data the data to import from (values > 0 are considered as 1)
     */
    importData(data: TypedArray): void {
        this.binaryMask.setData(data);
        this.connectedComponentsValid = false;
    }

    /**
     * exports the binary mask to a Uint8Array
     * @returns a Uint8Array with values == 255 for the values > 0 in the binary mask
     */
    exportData(): Uint8Array {
        return this.binaryMask.getData();
    }

    /**
     * draws drawing to the binary mask
     * @param drawing: reading the red channel of the canvas
     * @param paintSettings: settings for the paint mode
     */
    draw(drawing: ImageType, paintSettings: PaintSettings): void {
        this._drawMask(this.binaryMask, drawing, paintSettings);
        this.connectedComponentsValid = false;
    }

    protected _drawMask(mask: BinaryMask, drawing: ImageType, paintSettings: PaintSettings): void {
        const uniforms = {
            u_drawing: mask.getTextureForImage(drawing),
            u_paint: paintSettings.paint
        };
        if (paintSettings.dilateErode) {
            mask.passShader(this.shaders.erodeDilate, uniforms);
        } else {
            mask.passShader(this.shaders.draw, uniforms);
        }
    }
    /**
     * clears the binary mask (sets all values to 0)
     */
    clear(): void {
        this.binaryMask.clearData();
    }

    /**
     * disposes the binary mask (frees the memory)
     */
    dispose(): void {
        this.binaryMask.dispose();
    }

    get texture(): WebGLTexture {
        return this.binaryMask.texture;
    }

    get bitmask(): number {
        return this.binaryMask.bitmask;
    }

    protected getUniforms(uniforms: any): any {

        return {
            ...uniforms,
            u_binary_mask: this.texture,
            u_bitmask: this.bitmask,

            u_questionable_mask: this.texture,
            u_questionable_bitmask: 0,
            u_has_questionable_mask: false,
        }
    }

    render(renderTarget: RenderTarget, uniforms: any): void {
        this.shaders.renderBinary.pass(renderTarget, this.getUniforms(uniforms));
    }


    private connectedComponents: WebGLTexture | undefined;
    private connectedComponentsValid: boolean = false;


    computeConnectedComponents() {

        const data = this.binaryMask.getData();
        const { width, height } = this.image;
        const label = BlobExtraction(data, width, height);
        // label contains the connected components (0 = background, 1 = first component, 2 = second component, ...)

        // upload to texture
        const gl = this.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.connectedComponents!);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, label);

        this.connectedComponentsValid = true;
    }

    getConnectedComponents(): WebGLTexture {
        if (this.connectedComponents === undefined) {
            this.connectedComponents = createTextureR8UI(this.webgl.gl, this.image.width, this.image.height);
        }
        if (this.connectedComponentsValid == false) {
            this.computeConnectedComponents();
        }
        return this.connectedComponents;
    }

    renderConnectedComponents(renderTarget: RenderTarget, uniforms: any): void {
        uniforms = {
            ...uniforms,
            u_annotation: this.getConnectedComponents(),
            u_colors: colorsFlat
        }
        this.shaders.renderConnectedComponents.pass(renderTarget, uniforms);
    }
}

export class QuestionableSegmentation extends BinarySegmentation {
    _questionableMask: BinaryMask | null = null;

    constructor(image: AbstractImage) {
        super(image);
    }

    get questionableMask(): BinaryMask {
        if (!this._questionableMask) {
            this._questionableMask = this.webgl.binaryMaskManager.allocateMask(this.image.width, this.image.height);
        }
        return this._questionableMask!;
    }

    importImage(image: ImageType, importOptions: ImportOptions = { threshold: 0.5, channel: 0 }): void {
        const uniforms = {
            u_import: this.binaryMask.getTextureForImage(image),
            u_threshold: importOptions.threshold,
            u_import_channel: 0
        };
        // red channel to binary mask
        this.binaryMask.passShader(this.shaders.import, uniforms);
        // green channel to questionable mask
        uniforms.u_import_channel = 1;
        this.questionableMask.passShader(this.shaders.import, uniforms);
    }


    /**
    * exports the binary and questionable masks to a canvas (attached to the context)
    * writes:
    * - red (255,0,0,255) for values > 0 in the binary mask
    * - green (0,255,0,255) for values > 0 in the questionable mask
    * - black (0,0,0,255) for background (values == 0)
    * @param ctx the context to export to
    */
    exportImage(ctx: CanvasRenderingContext2D): void {
        const binaryData = this.binaryMask.getData();
        const questionableData = this.questionableMask.getData();
        const { width, height } = this.image;

        const imageData = ctx.getImageData(0, 0, width, height);
        const dataOut = imageData.data;
        for (let i = 0; i < width * height; i++) {
            const dataOutIndex = 4 * i;
            if (binaryData[i] > 0) {
                dataOut[dataOutIndex] = 255;
            }
            if (questionableData[i] > 0) {
                dataOut[dataOutIndex + 1] = 255;
            }
            dataOut[dataOutIndex + 2] = 0;
            dataOut[dataOutIndex + 3] = 255;
        }
        ctx.putImageData(imageData, 0, 0);
    }

    importQuestionableData(data: TypedArray): void {
        this.questionableMask.setData(data);
    }

    exportQuestionableData(): Uint8Array {
        return this.questionableMask.getData();
    }


    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        if (paintSettings.questionable) {
            this._drawMask(this.questionableMask, drawing, paintSettings);
        } else {
            super.draw(drawing, paintSettings);
        }
    }

    clear(): void {
        super.clear();
        this.questionableMask.clearData();
    }

    dispose(): void {
        super.dispose();
        this.questionableMask.dispose();
    }


    protected getUniforms(uniforms: any): any {
        return {
            ...super.getUniforms(uniforms),
            u_questionable_mask: this.questionableMask.texture,
            u_questionable_bitmask: this.questionableMask.bitmask,
            u_has_questionable_mask: true
        }
    }
}

export class ProbabilitySegmentation implements Segmentation {

    protected _data: TextureData | null = null;

    constructor(private readonly image: AbstractImage) {

    }

    get data(): TextureData {
        if (!this._data) {
            this._data = new TextureData(this.image.webgl.gl, this.image.width, this.image.height, 'R8');
        }
        return this._data!;
    }


    importImage(image: ImageType): void {
        const uniforms = {
            u_import: this.data.getTextureForImage(image)
        };
        this.data.passShader(this.image.webgl.shaders.importProbability, uniforms);
    }

    exportImage(ctx: CanvasRenderingContext2D): void {
        const data = this.data.data;
        const { width, height } = this.image;

        const imageData = ctx.getImageData(0, 0, width, height);
        const dataOut = imageData.data;
        for (let i = 0; i < width * height; i++) {
            const value = data[i];
            dataOut[4 * i] = value;
            dataOut[4 * i + 1] = value;
            dataOut[4 * i + 2] = value;
            dataOut[4 * i + 3] = 255;
        }
        ctx.putImageData(imageData, 0, 0);
    }
    importData(data: TypedArray): void {
        throw new Error("Method not implemented.");
    }
    exportData(): Uint8Array {
        throw new Error("Method not implemented.");
    }
    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        throw new Error("Method not implemented.");
    }
    clear(): void {
        throw new Error("Method not implemented.");
    }
    dispose(): void {
        throw new Error("Method not implemented.");
    }

    render(renderTarget: RenderTarget, uniforms: any): void {
        uniforms = {
            ...uniforms,
            u_annotation: this.data.texture
        }
        this.image.webgl.shaders.renderProbability.pass(renderTarget, uniforms);
    }
}

export class MultiClassSegmentation implements Segmentation {

    constructor(private readonly image: AbstractImage) {

    }

    importImage(image: ImageType): void {
        throw new Error("Method not implemented.");
    }
    exportImage(ctx: CanvasRenderingContext2D): void {
        throw new Error("Method not implemented.");
    }
    importData(data: TypedArray): void {
        throw new Error("Method not implemented.");
    }
    exportData(): Uint8Array {
        throw new Error("Method not implemented.");
    }
    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        throw new Error("Method not implemented.");
    }
    clear(): void {
        throw new Error("Method not implemented.");
    }
    dispose(): void {
        throw new Error("Method not implemented.");
    }
    render(renderTarget: RenderTarget, uniforms: any): void {
        throw new Error("Method not implemented.");
    }
}