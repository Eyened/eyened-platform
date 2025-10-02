import { ModelSegmentationsRepo, SegmentationsRepo } from "$lib/data/repos.svelte";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type { ModelSegmentationGET, SegmentationGET } from "../../types/openapi_types";
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
        readonly segmentation: SegmentationGET | ModelSegmentationGET,
        readonly scanNr: number,
    ) {
        console.log(segmentation)
        this.mask = new constructors[segmentation.data_representation](image, segmentation);
        this.history = new DrawingHistory<string>(new Base64Serializer(segmentation.data_type, image.width, image.height));
        this.isDrawing = this.initialize();
    }

    private async initialize() {
        const axis = this.segmentation.sparse_axis ?? undefined;
        let npyArray: NPYArray;
        if (this.segmentation.annotation_type == 'model_segmentation') {
            npyArray = await new ModelSegmentationsRepo('segmentation-state').getData(this.segmentation.id, { axis, scan_nr: this.scanNr }) as any;
        } else {
            npyArray = await new SegmentationsRepo('segmentation-state').getData(this.segmentation.id, { axis, scan_nr: this.scanNr }) as any;
        }
        this.mask.importData(npyArray.data as DrawingArray);
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

        const thisType = this.segmentation.data_representation as any;
        const otherType = other.segmentation.data_representation as any;
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
        const axis = (this.segmentation as any).sparse_axis ?? (this.segmentation as any).sparseAxis ?? 0;
        return new SegmentationsRepo('segmentation-state').updateData(this.segmentation.id, buffer, { axis, scan_nr: this.image.image_id.endsWith('proj') ? undefined as any : this.scanNr });

    }

    dispose() {
        this.mask.dispose();
        this.history.clear();
    }
}
