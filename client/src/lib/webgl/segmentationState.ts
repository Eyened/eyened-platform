import { getSegmentationData, getModelSegmentationData, updateSegmentationData } from "$lib/data/helpers";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type { ModelSegmentationGET, SegmentationGET, SegmentationDataRepresentation } from "../../types/openapi_types";
// SimpleDataRepresentation is a subset of SegmentationDataRepresentation
export type SimpleDataRepresentation = 'Binary' | 'DualBitMask' | 'Probability';
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory.svelte";
import { Base64Serializer } from "./imageEncoder";
import { BinaryMask, MultiClassMask, MultiLabelMask, ProbabilityMask, QuestionableMask, type DrawingArray, type Mask, type PaintSettings } from "./mask.svelte";
import { convert } from "./segmentationConverter";

type MaskConstructor = new (image: AbstractImage, segmentation: SegmentationGET) => Mask;
export const constructors: Record<'Binary' | 'DualBitMask' | 'Probability' | 'MultiClass' | 'MultiLabel', MaskConstructor> = {
    'Binary': BinaryMask,
    'DualBitMask': QuestionableMask,
    'Probability': ProbabilityMask,
    'MultiClass': MultiClassMask,
    'MultiLabel': MultiLabelMask,
}

// manages the segmentation state (history, mask) for a single scan
export class SegmentationState {

    protected history: DrawingHistory<string>;
    public readonly mask: Mask;

    private isDrawing = Promise.resolve();
    private hasInitialCheckpoint = false;

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET | ModelSegmentationGET,
        readonly scanNr: number,
        initialData?: DrawingArray,
    ) {
        this.mask = new constructors[segmentation.data_representation](image, segmentation as SegmentationGET);
        this.history = new DrawingHistory<string>(new Base64Serializer(segmentation.data_type, image.width, image.height));
        if (initialData) {
            this.mask.importData(initialData);
        } else {
            this.isDrawing = this.initialize();
        }
    }

    private ensureInitialCheckpoint() {
        if (!this.hasInitialCheckpoint) {
            this.history.checkpoint(this.mask.exportData());
            this.hasInitialCheckpoint = true;
        }
    }

    private async initialize() {
        // Load a single slice from the server
        const sparse_axis = this.segmentation.sparse_axis ?? undefined;
        const scan_nr = this.scanNr;
        
        let npyArray: NPYArray;
        if (this.segmentation.annotation_type == 'model_segmentation') {
            npyArray = await getModelSegmentationData(this.segmentation.id, { sparse_axis, scan_nr });
        } else {
            npyArray = await getSegmentationData(this.segmentation.id, { sparse_axis, scan_nr });
        }
        this.mask.importData(npyArray.data as DrawingArray);
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();
        this.mask.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    async importOther(other: Mask) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();

        const data = other.exportData();

        const thisType = this.segmentation.data_representation as SegmentationDataRepresentation;
        const otherType = other.segmentation.data_representation as SegmentationDataRepresentation;
        const threshold = (255 * (other.segmentation.threshold ?? 0.5));

        function isSimpleRepresentation(t: SegmentationDataRepresentation): t is SimpleDataRepresentation {
            return t === 'Binary' || t === 'DualBitMask' || t === 'Probability';
        }

        if (isSimpleRepresentation(thisType) && isSimpleRepresentation(otherType)) {
            const dataConverted = convert(data, otherType, thisType, threshold);
            this.mask.importData(dataConverted);
        } else if (thisType === otherType) {
            this.mask.importData(data);
        } else {
            console.warn("SegmentationState.importOther: conversion not supported", otherType, "->", thisType);
        }

        this.isDrawing = this.checkpoint();
    }

    async checkpoint() {
        const data = this.mask.exportData();
        await this.updateServer();
        this.history.checkpoint(data);
    }

    get canUndo() {
        return this.history.canUndo;
    }

    get canRedo() {
        return this.history.canRedo;
    }

    async undo() {
        const data = await this.history.undo();
        if (data) {
            this.mask.importData(data);
            await this.updateServer();
        }
    }

    async redo() {
        const data = await this.history.redo();
        if (data) {
            this.mask.importData(data);
            await this.updateServer();
        }
    }

    updateServer() {
        const data = this.mask.exportData();
        const buffer = encodeNpy(data, [this.image.height, this.image.width]);
        const sparse_axis = this.segmentation.sparse_axis ?? undefined;
        const scan_nr = this.image.image_id.endsWith('proj') ? undefined : this.scanNr;
        return updateSegmentationData(this.segmentation.id, buffer, { sparse_axis, scan_nr });
    }

    dispose() {
        this.mask.dispose();
        this.history.clear();
    }
}
