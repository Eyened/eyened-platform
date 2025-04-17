import type { Position2D } from "$lib/types";
import type { PixelShaderProgram } from "./FragmentShaderProgram";
import type { AbstractImage } from "./abstractImage";
import type { Annotation } from "$lib/datamodel/annotation";

import type { Segmentation } from "./SegmentationController";
import { ProbabilityData, Uint8ArrayToCanvasGray } from "./segmentationData";
import { SvelteMap } from "svelte/reactivity";

export class ProbabilitySegmentation implements Segmentation {

    public threshold = $state(0.5);
    private drawEnhanceShader: PixelShaderProgram;
    private drawHardShader: PixelShaderProgram;

    private data: ProbabilityData;

    // maps scanNr to the number of pixels in the segmentation
    pixelArea = new SvelteMap<number, number>();

    constructor(
        public readonly id: string,
        readonly image: AbstractImage,
        readonly annotation: Annotation) {
        this.data = new ProbabilityData(image);

        this.drawEnhanceShader = image.webgl.shaders.drawEnhance;
        this.drawHardShader = image.webgl.shaders.drawHard;
    }

    dispose(): void {
        this.data.dispose();
    }

    getTexture(scanNr: number) {
        return this.data.getTexture(scanNr);
    }

    _after_update(scanNr: number) {
        // called after import / draw / clear
        this.pixelArea.set(scanNr, this.countPixels(scanNr));
    }

    import(scanNr: number, canvas: HTMLCanvasElement): void {
        this.data.setBscanCanvas(scanNr, canvas);
        this._after_update(scanNr);
    }

    importOther(scanNr: number, other: Segmentation): void {
        const ctx = this.image.getIOCtx();
        other.export(scanNr, ctx);
        this.import(scanNr, ctx.canvas);
    }

    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {
        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_drawing: this.image.getTextureForCanvas(drawing),
            u_paint: settings.mode == 'paint',
            u_questionable: settings.questionable,
        };
        this.data.passShader(scanNr, this.drawHardShader, uniforms);
        this._after_update(scanNr);
    }

    clear(scanNr: number): void {
        this.data.setBscan(scanNr, new Uint8Array(this.image.width * this.image.height));
        this._after_update(scanNr);
    }

    export(scanNr: number, ctx: CanvasRenderingContext2D): void {
        const data = this.data.getBscan(scanNr);
        Uint8ArrayToCanvasGray(data, ctx);
    }

    public drawEnhance(scanNr: number, settings: {
        brushRadius: number,
        hardness: number,
        pressure: number,
        erase: boolean,
        enhance: boolean,
        point: Position2D
    }) {
        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_position: [settings.point.x, settings.point.y],
            u_enhance: settings.enhance,
            u_radius: settings.brushRadius,
            u_pressure: settings.pressure,
            u_hardness: settings.hardness,
            u_erase: settings.erase,
        }
        this.data.passShader(scanNr, this.drawEnhanceShader, uniforms);
        // no call to _after_update, as this is done in the endDraw
    }

    public endDraw(scanNr: number) {
        this.data.readBscanFromGPU(scanNr);
        this._after_update(scanNr);
    }

    countPixels(scanNr: number): number {
        const data = this.data.getBscan(scanNr);
        let count = 0;
        const t = 255 * this.threshold;
        for (let i = 0; i < data.length; i++) {
            if (data[i] > t) {
                count++;
            }
        }
        return count;
    }

}