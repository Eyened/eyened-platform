import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { AnnotationData, AnnotationPlane } from "$lib/datamodel/annotationData.svelte";
import type { DataRepresentation } from "$lib/datamodel/annotationType.svelte";
import type { AbstractImage } from "./abstractImage";
import type { Shaders } from "./shaders";
import type { WebGL } from "./webgl";

export interface Segmentation {
    id: string;
    annotation: Annotation;
    image: AbstractImage;
    width: number;
    height: number;
    depth: number;
    annotationPlane: AnnotationPlane;
    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void;
    clear(scanNr: number): void;
    export(scanNr: number, ctx: CanvasRenderingContext2D, dataRepresentation?: DataRepresentation): void;
    getData(scanNr: number): Uint8Array | Uint16Array | Uint32Array | Float32Array;    
    import(scanNr: number, canvas: HTMLCanvasElement): void;
    importOther(scanNr: number, other: Segmentation): void;
}

export abstract class BaseSegmentation implements Segmentation {
    public width: number;
    public height: number;
    public depth: number;
    protected webgl: WebGL;
    protected shaders: Shaders;

    constructor(
        public readonly id: string,
        public readonly image: AbstractImage,
        public readonly annotation: Annotation,
        readonly annotationPlane: AnnotationPlane
    ) { 
        // if (annotationPlane == 'PRIMARY') { // CFI or B-scan
        //     this.width = image.width;
        //     this.height = image.height;
        //     this.depth = 1;
        // } else if (annotationPlane == 'SECONDARY') { // enface
        //     this.width = image.width;
        //     this.height = image.depth;
        //     this.depth = 1;
        // } else if (annotationPlane == 'TERTIARY') { // across B-scans
        //     this.width = image.height;
        //     this.height = image.depth;
        //     this.depth = 1;
        // } else if (annotationPlane == 'VOLUME') {
        //     this.width = image.width;
        //     this.height = image.height;
        //     this.depth = image.depth;
        // } else {
        //     throw new Error(`Unsupported annotation plane: ${annotationPlane}`);
        // }
        this.width = image.width;
        this.height = image.height;
        this.depth = image.depth;
        this.webgl = image.webgl;
        this.shaders = this.webgl.shaders;
    }

    abstract draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void;
    abstract clear(scanNr: number): void;
    abstract export(scanNr: number, ctx: CanvasRenderingContext2D, dataRepresentation?: DataRepresentation): void;
    abstract getData(scanNr: number): Uint8Array | Uint16Array | Uint32Array | Float32Array;
    abstract import(scanNr: number, canvas: HTMLCanvasElement): void;
    abstract importOther(scanNr: number, other: Segmentation): void;
    abstract dispose(): void;
    abstract initialize(annotationData: AnnotationData, dataRaw: any): void;
} 