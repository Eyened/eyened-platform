import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type {
    ModelSegmentationGET,
    SegmentationGET,
} from "../../types/openapi_types";
import { getSegmentationData, getModelSegmentationData } from "../data/helpers";
import type { NPYArray } from "../utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import type { Mask, PaintSettings } from "./mask.svelte";
import { SegmentationState } from "./segmentationState.svelte";

// manages the segmentation states (one per scan) for a single segmentation
export class SegmentationItem {
    // mapping of scanNr to SegmentationState
    segmentationStates: SvelteMap<number, SegmentationState> = new SvelteMap();
    /** Scan indices with server data; updated on successful slice PUTs (API object stays static). */
    private readonly savedScanIndexSet = new SvelteSet<number>();
    readonly savedScanIndices = $derived.by(() =>
        [...this.savedScanIndexSet].sort((a, b) => a - b),
    );
    loading: boolean = $state(false);
    ready: Promise<void> | null = null;

    // Reactive threshold state for immediate UI updates
    threshold: number = $state(0.5);

    /** Called after a B-scan slice mask changes (draw, undo, redo, import). */
    onSliceChanged?: (scanNr: number) => void;

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET | ModelSegmentationGET,
    ) {
        // Initialize threshold from segmentation or default to 0.5
        this.threshold = this.segmentation.threshold ?? 0.5;

        if (Array.isArray(this.segmentation.scan_indices)) {
            for (const scanNr of this.segmentation.scan_indices) {
                this.savedScanIndexSet.add(scanNr);
            }
        }

        if (
            Array.isArray(this.segmentation.scan_indices) &&
            this.segmentation.scan_indices.length < 5
        ) {
            for (const scanNr of this.segmentation.scan_indices ??
                Array.from({ length: this.image.depth }, (_, i) => i)) {
                this.getSegmentationState(scanNr, true);
            }
        } else {
            this.ready = this.loadFull();
        }
    }

    private async loadFull(): Promise<void> {
        try {
            this.loading = true;

            // Don't pass axis/scan_nr when loading full volume
            // API requires both axis AND scan_nr together, or neither
            const array: NPYArray | null =
                this.segmentation.annotation_type === "model_segmentation"
                    ? await getModelSegmentationData(this.segmentation.id)
                    : await getSegmentationData(this.segmentation.id);
            if (array == null) {
                // 204: no data - create states for each scan index; each will fetch and set isEmptyForSlice
                const scanIndices =
                    this.segmentation.scan_indices ??
                    Array.from({ length: this.image.depth }, (_, i) => i);
                for (const scanNr of scanIndices) {
                    this.getSegmentationState(scanNr, true);
                }
                return;
            }
            const shape = array.shape as number[];
            // Expecting [depth, height, width]
            if (shape.length != 3) {
                throw new Error("Invalid shape: " + shape.join(", "));
            }
            const [depth, height, width] = shape;

            let planeSize = height * width;

            let scanIndices = this.segmentation.scan_indices;
            if (!scanIndices) {
                let length;
                if (
                    this.segmentation.sparse_axis == null ||
                    this.segmentation.sparse_axis == undefined
                ) {
                    length = this.image.depth;
                    planeSize = this.image.height * this.image.width;
                    if (
                        !this.segmentation.image_projection_matrix &&
                        (depth != this.image.depth ||
                            height != this.image.height ||
                            width != this.image.width)
                    ) {
                        throw new Error("Invalid shape: " + shape.join(", "));
                    }
                } else if (this.segmentation.sparse_axis == 0) {
                    // sparse along depth, slices of width x height
                    length = depth;
                    planeSize = height * width;
                    if (
                        !this.segmentation.image_projection_matrix &&
                        (height != this.image.height ||
                            width != this.image.width)
                    ) {
                        throw new Error("Invalid shape: " + shape.join(", "));
                    }
                } else if (this.segmentation.sparse_axis == 1) {
                    // sparse along height, slices of width x depth
                    length = height;
                    planeSize = width * depth;
                    if (
                        depth != this.image.height ||
                        width != this.image.width
                    ) {
                        throw new Error("Invalid shape: " + shape.join(", "));
                    }
                } else if (this.segmentation.sparse_axis == 2) {
                    // sparse along width, slices of depth x height
                    length = width;
                    planeSize = depth * height;
                    if (
                        height != this.image.height ||
                        depth != this.image.depth
                    ) {
                        throw new Error("Invalid shape: " + shape.join(", "));
                    }
                } else {
                    throw new Error(
                        "Invalid sparse axis: " + this.segmentation.sparse_axis,
                    );
                }
                scanIndices = Array.from({ length }, (_, i) => i);
            }
            for (const scanNr of scanIndices) {
                const start = scanNr * planeSize;
                const end = start + planeSize;
                const slice = (array.data as any).subarray(start, end);
                this.getSegmentationState(scanNr, true, slice);
                this.addSavedScanIndex(scanNr);
            }
        } catch (error) {
            console.error("SegmentationItem loadFull failed", error);
        } finally {
            this.loading = false;
        }
    }

    getMask(scanNr: number): Mask | undefined {
        return this.segmentationStates.get(scanNr)?.mask;
    }

    addSavedScanIndex(scanNr: number) {
        this.savedScanIndexSet.add(scanNr);
    }

    isEmptyForSlice(scanNr: number): boolean {
        const scanIndices = this.savedScanIndices;
        if (scanIndices.length > 0 && !scanIndices.includes(scanNr)) {
            return true;
        }
        const state = this.segmentationStates.get(scanNr);
        if (state?.isEmptyForSlice) {
            return true;
        }
        return false;
    }

    getSegmentationState(
        scanNr: number,
        create: boolean = false,
        initialData?: Uint8Array | Uint16Array | Uint32Array | Float32Array,
    ): SegmentationState | undefined {
        if (create && !this.segmentationStates.has(scanNr)) {
            const segmentationState = new SegmentationState(
                this.image,
                this.segmentation,
                scanNr,
                initialData,
                this,
            );
            this.segmentationStates.set(scanNr, segmentationState);
        }
        return this.segmentationStates.get(scanNr)!;
    }

    async importOther(scanNr: number, mask: Mask) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        segmentationState.importOther(mask);
    }

    async draw(
        scanNr: number,
        drawing: HTMLCanvasElement,
        settings: PaintSettings,
    ) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        await segmentationState.draw(drawing, settings);
    }

    async undo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            await segmentationState.undo();
        } else {
            console.warn(
                "SegmentationItem.undo: segmentationState not found",
                scanNr,
            );
        }
    }

    async redo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            await segmentationState.redo();
        } else {
            console.warn(
                "SegmentationItem.redo: segmentationState not found",
                scanNr,
            );
        }
    }

    notifySliceChanged(scanNr: number): void {
        this.onSliceChanged?.(scanNr);
    }

    dispose() {
        // Note: not called currently
        for (const segmentationState of this.segmentationStates.values()) {
            segmentationState.dispose();
        }
        this.segmentationStates.clear();
    }
}
