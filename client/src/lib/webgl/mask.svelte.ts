import { BlobExtraction } from "$lib/image-processing/connected-component-labelling";
import type { Position2D } from "$lib/types";
import { colorsFlat } from "$lib/viewer/overlays/colors";
import type { SegmentationGET } from "../../types/openapi_types";
import type { AbstractImage } from "./abstractImage";
import { segmentationPlaneSize } from "./segmentationProjection";
import type { TextureShaderProgram } from "./FragmentShaderProgram";
import type { Shaders } from "./shaders";
import {
    BitMaskTexture,
    createTextureR8UI,
    imageToTexture,
    TextureData,
    type ImageType,
} from "./texture";
import type { RenderTarget, ShaderUniforms } from "./types";
import type { WebGL } from "./webgl";

export type DrawingArray =
    | Uint8Array
    | Uint16Array
    | Uint32Array
    | Float32Array;

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

export type MaskRenderUniforms = ShaderUniforms & {
    activeIndices?: number | number[];
};

export abstract class Mask {
    readonly planeWidth: number;
    readonly planeHeight: number;

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET,
    ) {
        const plane = segmentationPlaneSize(segmentation, image);
        this.planeWidth = plane.width;
        this.planeHeight = plane.height;
    }

    abstract importData(data: DrawingArray): void;
    abstract exportData(): DrawingArray;
    abstract draw(drawing: ImageType, paintSettings: PaintSettings): void;
    abstract clear(): void;
    abstract dispose(): void;
    abstract render(
        renderTarget: RenderTarget,
        uniforms: MaskRenderUniforms,
    ): void;
}

export class BinaryMask extends Mask {
    protected _binaryMask: BitMaskTexture | null = null;
    protected webgl: WebGL;
    protected shaders: Shaders;
    public pixelArea: number = $state(0);

    constructor(image: AbstractImage, segmentation: SegmentationGET) {
        super(image, segmentation);
        this.webgl = this.image.webgl;
        this.shaders = this.webgl.shaders;
    }

    get bitMaskTexture(): BitMaskTexture {
        if (!this._binaryMask) {
            this._binaryMask = this.webgl.binaryMaskManager.allocateMask(
                this.planeWidth,
                this.planeHeight,
            );
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

    protected _drawMask(
        mask: BitMaskTexture,
        drawing: ImageType,
        paintSettings: PaintSettings,
    ): void {
        const drawingTexture = imageToTexture(this.webgl.gl, drawing);
        if (paintSettings.dilateErode) {
            mask.passShader(this.shaders.erodeDilate, {
                u_drawing: drawingTexture,
                u_dilate: paintSettings.paint,
                u_is_multi_label: true, // binary masks store foreground as a single bit
                u_active_feature: mask.bitmask,
            });
        } else {
            mask.passShader(this.shaders.draw, {
                u_drawing: drawingTexture,
                u_paint: paintSettings.paint,
                u_mode: true, // multi-label logic is used for binary masks
            });
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

    protected getRenderUniforms(uniforms: MaskRenderUniforms): ShaderUniforms {
        return {
            ...uniforms,
            u_binary_mask: this.texture,
            u_bitmask: this.bitmask,

            u_questionable_mask: this.texture,
            u_questionable_bitmask: 0,
            u_has_questionable_mask: false,
        };
    }

    render(renderTarget: RenderTarget, uniforms: MaskRenderUniforms): void {
        this.shaders.renderBinary.pass(
            renderTarget,
            this.getRenderUniforms(uniforms),
        );
    }

    private connectedComponents: WebGLTexture | undefined;
    private connectedComponentsValid: boolean = false;

    computeConnectedComponents() {
        const data = this.bitMaskTexture.getData();
        const label = BlobExtraction(data, this.planeWidth, this.planeHeight);
        // label contains the connected components (0 = background, 1 = first component, 2 = second component, ...)

        // upload to texture
        const gl = this.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.connectedComponents!);
        gl.texImage2D(
            gl.TEXTURE_2D,
            0,
            gl.R8UI,
            this.planeWidth,
            this.planeHeight,
            0,
            gl.RED_INTEGER,
            gl.UNSIGNED_BYTE,
            label,
        );

        this.connectedComponentsValid = true;
    }

    getConnectedComponents(): WebGLTexture {
        if (this.connectedComponents === undefined) {
            this.connectedComponents = createTextureR8UI(
                this.webgl.gl,
                this.planeWidth,
                this.planeHeight,
            );
        }
        if (this.connectedComponentsValid == false) {
            this.computeConnectedComponents();
        }
        return this.connectedComponents;
    }

    renderConnectedComponents(
        renderTarget: RenderTarget,
        uniforms: MaskRenderUniforms,
    ): void {
        const { activeIndices: _activeIndices, ...baseUniforms } = uniforms;
        const renderUniforms: ShaderUniforms = {
            ...baseUniforms,
            u_annotation: this.getConnectedComponents(),
            u_colors: colorsFlat,
        };
        this.shaders.renderConnectedComponents.pass(
            renderTarget,
            renderUniforms,
        );
    }
}

export class QuestionableMask extends BinaryMask {
    _questionableMask: BitMaskTexture | null = null;

    constructor(image: AbstractImage, segmentation: SegmentationGET) {
        super(image, segmentation);
    }

    get questionableMask(): BitMaskTexture {
        if (!this._questionableMask) {
            this._questionableMask = this.webgl.binaryMaskManager.allocateMask(
                this.planeWidth,
                this.planeHeight,
            );
        }
        return this._questionableMask!;
    }

    importData(data: DrawingArray): void {
        const planeSize = this.planeWidth * this.planeHeight;
        const b = new Uint8Array(planeSize);
        const q = new Uint8Array(planeSize);
        for (let i = 0; i < planeSize; i++) {
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
        const planeSize = this.planeWidth * this.planeHeight;
        const result = new Uint8Array(planeSize);
        const q = this.questionableMask.getData();
        const b = this.bitMaskTexture.getData();
        for (let i = 0; i < planeSize; i++) {
            let bitmask = 0;
            if (b[i] > 0) {
                bitmask |= 1;
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

    protected getRenderUniforms(uniforms: MaskRenderUniforms): ShaderUniforms {
        return {
            ...super.getRenderUniforms(uniforms),
            u_questionable_mask: this.questionableMask.texture,
            u_questionable_bitmask: this.questionableMask.bitmask,
            u_has_questionable_mask: true,
        };
    }
}
abstract class AbstractDataMask extends Mask {
    textureData: TextureData;
    constructor(image: AbstractImage, segmentation: SegmentationGET) {
        super(image, segmentation);
        const dataType = segmentation.data_type;
        this.textureData = new TextureData(
            image.webgl.gl,
            this.planeWidth,
            this.planeHeight,
            dataType,
        );
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
    constructor(image: AbstractImage, segmentation: SegmentationGET) {
        super(image, segmentation);
    }

    computePixelArea(threshold: number): number {
        const data = this.textureData.data;
        const dataType = this.segmentation.data_type;
        let count = 0;
        if (dataType === "R32F") {
            for (let i = 0; i < data.length; i++) {
                if ((data as Float32Array)[i] > threshold) {
                    count++;
                }
            }
        } else {
            const t = 255 * threshold;
            for (let i = 0; i < data.length; i++) {
                if ((data as Uint8Array)[i] > t) {
                    count++;
                }
            }
        }
        return count;
    }

    private afterUpdate(threshold: number) {
        this.pixelArea = this.computePixelArea(threshold);
    }

    importData(data: DrawingArray): void {
        super.importData(data);
        this.afterUpdate(this.segmentation.threshold ?? 0.5);
    }

    clear(): void {
        super.clear();
        this.afterUpdate(this.segmentation.threshold ?? 0.5);
    }

    drawEnhance(settings: {
        radiusX: number;
        radiusY: number;
        hardness: number;
        pressure: number;
        erase: boolean;
        point: Position2D;
    }): void {
        const uniforms = {
            u_current: this.textureData.texture,
            u_position: [settings.point.x, settings.point.y],
            u_radius: [settings.radiusX, settings.radiusY],
            u_pressure: settings.pressure,
            u_hardness: settings.hardness,
            u_erase: settings.erase,
            u_aspectRatio: 1.0,
        };
        this.u_hard = false;
        this.textureData.passShader(
            this.image.webgl.shaders.drawEnhance,
            uniforms,
        );
        this.afterUpdate(this.segmentation.threshold ?? 0.5);
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
            u_questionable: paintSettings.questionable,
        };
        this.textureData.passShader(
            this.image.webgl.shaders.drawHard,
            uniforms,
        );
        this.afterUpdate(this.segmentation.threshold ?? 0.5);
    }

    render(renderTarget: RenderTarget, uniforms: MaskRenderUniforms): void {
        const { activeIndices: _activeIndices, ...baseUniforms } = uniforms;
        const renderUniforms: ShaderUniforms = {
            ...baseUniforms,
            u_annotation: this.textureData.texture,
            u_hard: this.u_hard,
        };
        this.image.webgl.shaders.renderProbability.pass(
            renderTarget,
            renderUniforms,
        );
    }
}

abstract class BaseMultiMask extends AbstractDataMask {
    constructor(image: AbstractImage, segmentation: SegmentationGET) {
        super(image, segmentation);
    }

    abstract getBitmask(activeIndex: number | number[]): number;
    abstract getRenderShader(): TextureShaderProgram;

    draw(drawing: HTMLCanvasElement, paintSettings: PaintSettings): void {
        if (!paintSettings.activeIndices) {
            console.warn("MultiLabelSegmentation: no active indices");
            return;
        }
        const activeFeature = this.getBitmask(paintSettings.activeIndices);
        const isMultiLabel =
            this.segmentation.data_representation == "MultiLabel";
        const drawingTexture = imageToTexture(this.image.webgl.gl, drawing);
        if (paintSettings.dilateErode) {
            this.textureData.passShader(this.image.webgl.shaders.erodeDilate, {
                u_current: this.textureData.texture,
                u_drawing: drawingTexture,
                u_dilate: paintSettings.paint,
                u_is_multi_label: isMultiLabel,
                u_active_feature: activeFeature,
            });
        } else {
            this.textureData.passShader(this.image.webgl.shaders.draw, {
                u_current: this.textureData.texture,
                u_drawing: drawingTexture,
                u_paint: paintSettings.paint,
                u_bitmask: activeFeature,
                u_mode: isMultiLabel,
            });
        }
    }

    clear(): void {
        this.textureData.clearData();
    }

    dispose(): void {
        this.textureData.dispose();
    }

    render(renderTarget: RenderTarget, uniforms: MaskRenderUniforms): void {
        const { activeIndices, ...baseUniforms } = uniforms;
        const renderUniforms: ShaderUniforms = {
            ...baseUniforms,
            u_annotation: this.textureData.texture,
            u_colors: colorsFlat,
            u_boundaries: undefined,
            u_active_feature_mask: this.getBitmask(activeIndices ?? []),
        };
        this.getRenderShader().pass(renderTarget, renderUniforms);
    }
}
export class MultiClassMask extends BaseMultiMask {
    constructor(image: AbstractImage, segmentation: SegmentationGET) {
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
    constructor(image: AbstractImage, segmentation: SegmentationGET) {
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
