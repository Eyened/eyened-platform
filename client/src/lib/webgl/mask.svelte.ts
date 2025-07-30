import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import { BlobExtraction } from "$lib/image-processing/connected-component-labelling";
import type { Position2D } from "$lib/types";
import { colorsFlat } from "$lib/viewer/overlays/colors";
import type { AbstractImage } from "./abstractImage";
import type { TextureShaderProgram } from "./FragmentShaderProgram";
import type { Shaders } from "./shaders";
import { imageToTexture, createTextureR8UI, TextureData, type ImageType, BitMaskTexture } from "./texture";
import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";

export type DrawingArray = Uint8Array | Uint16Array | Uint32Array | Float32Array;

export interface ImportOptions {
    threshold?: number;
    channel?: number;
}

export interface PaintSettings {
    paint?: boolean;
    dilateErode?: boolean;
    questionable?: boolean;
    activeIndices?: number | number[];
}

export abstract class Mask {
    constructor(
        readonly image: AbstractImage,
        readonly segmentation: Segmentation
    ) { }

    abstract importData(data: DrawingArray): void;
    abstract exportData(): DrawingArray;
    abstract draw(drawing: ImageType, paintSettings: PaintSettings): void;
    abstract clear(): void;
    abstract dispose(): void;
    abstract render(renderTarget: RenderTarget, uniforms: any): void;
}


export class BinaryMask extends Mask {

    protected _binaryMask: BitMaskTexture | null = null;
    protected webgl: WebGL;
    protected shaders: Shaders;
    public pixelArea: number = $state(0);

    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
        this.webgl = this.image.webgl;
        this.shaders = this.webgl.shaders;
    }

    get bitMaskTexture(): BitMaskTexture {
        if (!this._binaryMask) {
            this._binaryMask = this.webgl.binaryMaskManager.allocateMask(this.image.width, this.image.height);
        }
        return this._binaryMask!;
    }

    protected afterUpdate() {
        this.connectedComponentsValid = false;
        const d = this.bitMaskTexture.getData();
        this.pixelArea = d.reduce((acc, curr) => acc + curr, 0);
    }

    importData(data: DrawingArray): void {
        this.bitMaskTexture.setData(data);
        this.afterUpdate();
    }

    /**
     * exports the binary mask to a Uint8Array
     * @returns a Uint8Array with 1 for foreground pixels and 0 for background pixels
     */
    exportData(): Uint8Array {
        return this.bitMaskTexture.getData(1);
    }

    /**
     * draws drawing to the binary mask
     * @param drawing: reading the red channel of the canvas
     * @param paintSettings: settings for the paint mode
     */
    draw(drawing: ImageType, paintSettings: PaintSettings): void {
        this._drawMask(this.bitMaskTexture, drawing, paintSettings);
    }

    protected _drawMask(mask: BitMaskTexture, drawing: ImageType, paintSettings: PaintSettings): void {
        const uniforms = {
            u_drawing: imageToTexture(this.webgl.gl, drawing),
            u_paint: paintSettings.paint,
            u_mode: true // multi-label logic is used for binary masks
        };
        if (paintSettings.dilateErode) {
            mask.passShader(this.shaders.erodeDilate, uniforms);
        } else {
            mask.passShader(this.shaders.draw, uniforms);
        }
        this.afterUpdate();
    }

    clear(): void {
        this.bitMaskTexture.clearData();
        this.afterUpdate();
    }

    dispose(): void {
        this.bitMaskTexture.dispose();
    }

    get texture(): WebGLTexture {
        return this.bitMaskTexture.texture;
    }

    get bitmask(): number {
        return this.bitMaskTexture.bitmask;
    }

    protected getRenderUniforms(uniforms: any): any {

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
        this.shaders.renderBinary.pass(renderTarget, this.getRenderUniforms(uniforms));
    }


    private connectedComponents: WebGLTexture | undefined;
    private connectedComponentsValid: boolean = false;


    computeConnectedComponents() {
        const data = this.bitMaskTexture.getData();
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

export class QuestionableMask extends BinaryMask {
    _questionableMask: BitMaskTexture | null = null;

    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
    }

    get questionableMask(): BitMaskTexture {
        if (!this._questionableMask) {
            this._questionableMask = this.webgl.binaryMaskManager.allocateMask(this.image.width, this.image.height);
        }
        return this._questionableMask!;
    }

    importData(data: DrawingArray): void {
        const b = new Uint8Array(this.image.width * this.image.height);
        const q = new Uint8Array(this.image.width * this.image.height);
        for (let i = 0; i < this.image.width * this.image.height; i++) {
            b[i] = data[i] & 1;
            q[i] = (data[i] >> 1) & 1;
        }
        this.bitMaskTexture.setData(b);
        this.questionableMask.setData(q);
        this.afterUpdate();
    }

    /**
     * exports the questionable mask to a Uint8Array
     * @returns a Uint8Array with bitmask 1 for annotated pixels, bitmask 2 (1<<1) for questionable pixels and 0 for background pixels
     */
    exportData(): Uint8Array {
        const result = new Uint8Array(this.image.width * this.image.height);
        const q = this.questionableMask.getData();
        const b = this.bitMaskTexture.getData();
        for (let i = 0; i < this.image.width * this.image.height; i++) {
            let bitmask = 0;
            if (b[i] > 0) {
                bitmask |= 1
            }
            if (q[i] > 0) {
                bitmask |= 1 << 1;
            }
            result[i] = bitmask;
        }
        return result;
    }


    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        if (paintSettings.questionable) {
            this._drawMask(this.questionableMask, drawing, paintSettings);

        } else {
            super.draw(drawing, paintSettings);
        }

    }

    clear(): void {
        this.questionableMask.clearData();
        super.clear();
    }

    dispose(): void {
        this.questionableMask.dispose();
        super.dispose();
    }


    protected getRenderUniforms(uniforms: any): any {
        return {
            ...super.getRenderUniforms(uniforms),
            u_questionable_mask: this.questionableMask.texture,
            u_questionable_bitmask: this.questionableMask.bitmask,
            u_has_questionable_mask: true
        }
    }
}
abstract class AbstractDataMask extends Mask {
    textureData: TextureData;
    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
        const dataType = segmentation.dataType;
        this.textureData = new TextureData(image.webgl.gl, image.width, image.height, dataType);
    }

    importData(data: DrawingArray): void {
        this.textureData.uploadData(data);
    }

    exportData(): DrawingArray {
        return this.textureData.data;
    }

    clear(): void {
        this.textureData.clearData();
    }

    dispose(): void {
        this.textureData.dispose();
    }
}

export class ProbabilityMask extends AbstractDataMask {
    public pixelArea: number = $state(0);

    u_hard: boolean = true;
    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
    }

    drawEnhance(settings: {
        brushRadius: number,
        hardness: number,
        pressure: number,
        erase: boolean,
        enhance: boolean,
        point: Position2D,
        aspectRatio: number
    }): void {

        const uniforms = {
            u_current: this.textureData.texture,
            u_position: [settings.point.x, settings.point.y],
            u_enhance: settings.enhance,
            u_radius: settings.brushRadius,
            u_pressure: settings.pressure,
            u_hardness: settings.hardness,
            u_erase: settings.erase,
            u_aspectRatio: settings.aspectRatio
        }
        this.u_hard = false;
        this.textureData.passShader(this.image.webgl.shaders.drawEnhance, uniforms);
    }

    draw(drawing: ImageType, paintSettings: PaintSettings): void {
        // TODO: this is a hack to make the enhance tool work
        if (!drawing) {
            this.u_hard = true;
            return;
        }
        const uniforms = {
            u_current: this.textureData.texture,
            u_drawing: imageToTexture(this.image.webgl.gl, drawing),
            u_paint: paintSettings.paint,
            u_questionable: paintSettings.questionable
        };
        this.textureData.passShader(this.image.webgl.shaders.drawHard, uniforms);
    }

    render(renderTarget: RenderTarget, uniforms: any): void {
        uniforms = {
            ...uniforms,
            u_annotation: this.textureData.texture,
            u_hard: this.u_hard
        }
        this.image.webgl.shaders.renderProbability.pass(renderTarget, uniforms);
    }
}

abstract class BaseMultiMask extends AbstractDataMask {

    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
    }

    abstract getBitmask(activeIndex: number | number[]): number;
    abstract getRenderShader(): TextureShaderProgram;

    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        if (!paintSettings.activeIndices) {
            console.warn("MultiLabelSegmentation: no active indices");
            return;
        }
        const bitmask = this.getBitmask(paintSettings.activeIndices);
        const uniforms = {
            u_current: this.textureData.texture,
            u_drawing: imageToTexture(this.image.webgl.gl, drawing),
            u_paint: paintSettings.paint,
            u_bitmask: bitmask,
            u_mode: this.segmentation.dataRepresentation == 'MultiLabel'
        };
        if (paintSettings.dilateErode) {
            //TODO: implement erodeDilate for multi-label segmentation
        } else {
            this.textureData.passShader(this.image.webgl.shaders.draw, uniforms);
        }
    }

    clear(): void {
        this.textureData.clearData();
    }

    dispose(): void {
        this.textureData.dispose();
    }

    render(renderTarget: RenderTarget, uniforms: any): void {
        uniforms = {
            ...uniforms,
            u_annotation: this.textureData.texture,
            u_colors: colorsFlat,
            u_boundaries: undefined,
            u_active_feature_mask: this.getBitmask(uniforms.activeIndices)
        }
        this.getRenderShader().pass(renderTarget, uniforms);
    }
}
export class MultiClassMask extends BaseMultiMask {
    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
    }
    getBitmask(activeIndex: number[] | number): number {
        if (Array.isArray(activeIndex)) {
            // empty array when not set yet
            return 0;
        }
        return activeIndex;
    }
    getRenderShader() {
        return this.image.webgl.shaders.renderMultiClass;
    }
}

export class MultiLabelMask extends BaseMultiMask {
    constructor(image: AbstractImage, segmentation: Segmentation) {
        super(image, segmentation);
    }
    getBitmask(activeIndices: number[] | number): number {
        let bitmask = 0;
        if (Array.isArray(activeIndices)) {
            for (const i of activeIndices) {
                bitmask |= 1 << (i - 1);
            }
            return bitmask;
        } else {
            return 1 << (activeIndices - 1);
        }
    }

    getRenderShader() {
        return this.image.webgl.shaders.renderMultiLabel;
    }
}