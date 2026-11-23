import {
    getSegmentationData,
    getModelSegmentationData,
    updateSegmentationData,
} from "$lib/data/helpers";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type {
    ModelSegmentationGET,
    SegmentationGET,
} from "../../types/openapi_types";
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory.svelte";
import { Base64Serializer } from "./imageEncoder";
import {
    BinaryMask,
    MultiClassMask,
    MultiLabelMask,
    ProbabilityMask,
    QuestionableMask,
    type DrawingArray,
    type Mask,
    type PaintSettings,
} from "./mask.svelte";
import type { SegmentationItem } from "./segmentationItem.svelte";
import { prepareImportedMask } from "./segmentationTransfer";
import { segmentationPlaneSize } from "./segmentationProjection";

type MaskConstructor = new (
    image: AbstractImage,
    segmentation: SegmentationGET,
) => Mask;
export const constructors: Record<
    "Binary" | "DualBitMask" | "Probability" | "MultiClass" | "MultiLabel",
    MaskConstructor
> = {
    Binary: BinaryMask,
    DualBitMask: QuestionableMask,
    Probability: ProbabilityMask,
    MultiClass: MultiClassMask,
    MultiLabel: MultiLabelMask,
};

// manages the segmentation state (history, mask) for a single scan

export class SegmentationState {
    protected history: DrawingHistory<string>;
    public readonly mask: Mask;

    private isDrawing = Promise.resolve();
    private hasInitialCheckpoint = false;
    /** Sends the mask 2 s after the last change; the mask is exported when it is sent. */
    public readonly saver: DebouncedSaver<void>;
    public isEmptyForSlice = $state(false);
    /** Settles when this slice's first fetch is done; resolved at once when it started with data. */
    public readonly loaded: Promise<void>;

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET | ModelSegmentationGET,
        readonly scanNr: number,
        initialData?: DrawingArray,
        readonly segmentationItem?: SegmentationItem,
    ) {
        this.mask = new constructors[segmentation.data_representation](
            image,
            segmentation as SegmentationGET,
        );
        const plane = segmentationPlaneSize(segmentation, image);
        this.history = new DrawingHistory<string>(
            new Base64Serializer(
                segmentation.data_type,
                plane.width,
                plane.height,
            ),
        );
        if (initialData) {
            this.mask.importData(initialData);
        } else {
            this.isDrawing = this.initialize();
        }
        this.loaded = this.isDrawing;
        this.saver = new DebouncedSaver<void>({
            kind: "segmentation",
            group: `${segmentation.annotation_type}_${segmentation.id}`,
            target: {
                to: "layers",
                section: "segmentations",
                imageId: image.image_id,
                item: { kind: "segmentation", segmentation },
            },
            delay: 2000,
            send: () => this.send(),
        });
    }

    /** Takes the slice's first history entry, so a stroke that writes live can still be undone. */
    ensureInitialCheckpoint() {
        if (!this.hasInitialCheckpoint) {
            this.history.checkpoint(this.mask.exportData());
            this.hasInitialCheckpoint = true;
        }
    }

    private notifySliceChanged(): void {
        this.segmentationItem?.notifySliceChanged(this.scanNr);
    }

    private async initialize() {
        // Load a single slice from the server
        const sparse_axis = this.segmentation.sparse_axis ?? undefined;
        const scan_nr = this.scanNr;

        let npyArray: NPYArray | null;
        if (this.segmentation.annotation_type == "model_segmentation") {
            npyArray = await getModelSegmentationData(this.segmentation.id, {
                sparse_axis,
                scan_nr,
            });
        } else {
            npyArray = await getSegmentationData(this.segmentation.id, {
                sparse_axis,
                scan_nr,
            });
        }
        if (npyArray == null) {
            this.isEmptyForSlice = true;
            return;
        }
        this.mask.importData(npyArray.data as DrawingArray);
        this.segmentationItem?.addSavedScanIndex(scan_nr);
        this.notifySliceChanged();
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();
        this.mask.draw(drawing, settings);
        // The slice now has user content, whatever the server said on load.
        this.isEmptyForSlice = false;
        this.notifySliceChanged();
        this.isDrawing = this.checkpoint();
    }

    async importOther(other: Mask) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();

        const data = prepareImportedMask({
            data: other.exportData(),
            sourceWidth: other.planeWidth,
            sourceHeight: other.planeHeight,
            destWidth: this.mask.planeWidth,
            destHeight: this.mask.planeHeight,
            sourceRepresentation: other.segmentation.data_representation,
            destRepresentation: this.segmentation.data_representation,
            sourceMatrix: other.segmentation.image_projection_matrix,
            destMatrix: this.segmentation.image_projection_matrix,
            threshold: 255 * (other.segmentation.threshold ?? 0.5),
        });
        if (data) {
            this.mask.importData(data);
        } else {
            console.warn(
                "SegmentationState.importOther: conversion not supported",
                other.segmentation.data_representation,
                "->",
                this.segmentation.data_representation,
            );
        }

        this.isEmptyForSlice = false;
        this.notifySliceChanged();
        this.isDrawing = this.checkpoint();
    }

    async checkpoint() {
        const data = this.mask.exportData();
        this.saver.edit();
        this.history.checkpoint(data);
    }

    get canUndo() {
        return this.history.canUndo;
    }

    get canRedo() {
        return this.history.canRedo;
    }

    async undo() {
        await this.isDrawing; // the stroke's own checkpoint must land before it is undone
        const data = await this.history.undo();
        if (data) {
            this.mask.importData(data);
            this.notifySliceChanged();
            this.saver.edit();
        }
    }

    async redo() {
        const data = await this.history.redo();
        if (data) {
            this.mask.importData(data);
            this.notifySliceChanged();
            this.saver.edit();
        }
    }

    private async send(): Promise<void> {
        const data = this.mask.exportData();
        const { planeHeight, planeWidth } = this.mask;
        const expectedLen = planeHeight * planeWidth;
        if (data.length !== expectedLen && data.length !== expectedLen * 4) {
            console.error("Segmentation save: data length mismatch", {
                got: data.length,
                expected: expectedLen,
                planeWidth,
                planeHeight,
            });
        }
        const buffer = encodeNpy(data, [planeHeight, planeWidth]);
        const sparse_axis = this.segmentation.sparse_axis ?? undefined;
        let scan_nr: number | undefined = this.scanNr;
        if (this.image.image_id.endsWith("proj")) {
            scan_nr = undefined;
        }
        if (scan_nr !== undefined) {
            this.segmentationItem?.addSavedScanIndex(scan_nr);
        }
        const resp = await updateSegmentationData(
            this.segmentation.id,
            buffer,
            { sparse_axis, scan_nr },
        );
        await resp.json();
    }

    dispose() {
        // The saver exports the mask as it sends, before the mask goes.
        this.saver.dispose();
        this.mask.dispose();
        this.history.clear();
    }
}
