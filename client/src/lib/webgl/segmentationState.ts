import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import { encodeNpy } from "$lib/utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory.svelte";
import { Base64Serializer } from "./imageEncoder";
import { BinaryMask, MultiClassMask, MultiLabelMask, ProbabilityMask, QuestionableMask, type DrawingArray, type Mask, type PaintSettings } from "./mask.svelte";
import { convert } from "./segmentationConverter";

export const constructors = {
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

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: Segmentation,
        readonly scanNr: number,
    ) {
        this.mask = new constructors[segmentation.dataRepresentation](image, segmentation);
        this.history = new DrawingHistory<string>(new Base64Serializer(segmentation.dataType, image.width, image.height));
        this.isDrawing = this.initialize();
    }

    private async initialize() {
        const array = await this.segmentation.loadData(this.scanNr);
        this.mask.importData(array.data as DrawingArray);
        this.history.checkpoint(this.mask.exportData());
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.mask.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    async importOther(other: Mask) {
        await this.isDrawing; // wait for previous drawing to finish

        const data = other.exportData();

        const thisType = this.segmentation.dataRepresentation;
        const otherType = other.segmentation.dataRepresentation;
        const threshold = (255 * (other.segmentation.threshold ?? 0.5));

        const dataConverted = convert(data, otherType, thisType, threshold);
        this.mask.importData(dataConverted);

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
        if (this.image.image_id.endsWith('proj')) {
            return this.segmentation.updateData(null, buffer);
        } else {
            return this.segmentation.updateData(this.scanNr, buffer);
        }

    }

    dispose() {
        this.mask.dispose();
        this.history.clear();
    }
}
