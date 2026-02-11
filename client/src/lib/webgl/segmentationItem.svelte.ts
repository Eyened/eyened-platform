import { SvelteMap } from "svelte/reactivity";
import type { ModelSegmentationGET, SegmentationGET } from "../../types/openapi_types";
import { getSegmentationData, getModelSegmentationData } from "../data/helpers";
import type { NPYArray } from "../utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import type { Mask, PaintSettings } from "./mask.svelte";
import { SegmentationState } from "./segmentationState.svelte";
import { TextureData } from "./texture";

// manages the segmentation states (one per scan) for a single segmentation
export class SegmentationItem {

    // mapping of scanNr to SegmentationState
    segmentationStates: SvelteMap<number, SegmentationState> = new SvelteMap();
    loading: boolean = $state(false);
    ready: Promise<void> | null = null;

    // Reactive threshold state for immediate UI updates
    threshold: number = $state(0.5);

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET | ModelSegmentationGET) {

        // Initialize threshold from segmentation or default to 0.5
        this.threshold = this.segmentation.threshold ?? 0.5;

        if (Array.isArray(this.segmentation.scan_indices) && this.segmentation.scan_indices.length < 5) {
            for (const scanNr of this.segmentation.scan_indices ?? Array.from({ length: this.image.depth }, (_, i) => i)) {
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
            const array: (NPYArray | null) = this.segmentation.annotation_type === 'model_segmentation'
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
                throw new Error('Invalid shape: ' + shape.join(', '));
            }
            const [depth, height, width] = shape;

            let planeSize = height * width;

            let scanIndices = this.segmentation.scan_indices;
            if (!scanIndices) {
                let length;
                if (this.segmentation.sparse_axis == null || this.segmentation.sparse_axis == undefined) {
                    length = this.image.depth;
                    planeSize = this.image.height * this.image.width;
                    if (depth != this.image.depth || height != this.image.height || width != this.image.width) {
                        throw new Error('Invalid shape: ' + shape.join(', '));
                    }
                } else if (this.segmentation.sparse_axis == 0) {
                    // sparse along depth, slices of width x height
                    length = depth;
                    planeSize = height * width;
                    if (height != this.image.height || width != this.image.width) {
                        throw new Error('Invalid shape: ' + shape.join(', '));
                    }
                } else if (this.segmentation.sparse_axis == 1) {
                    // sparse along height, slices of width x depth
                    length = height;
                    planeSize = width * depth;
                    if (depth != this.image.height || width != this.image.width) {
                        throw new Error('Invalid shape: ' + shape.join(', '));
                    }
                } else if (this.segmentation.sparse_axis == 2) {
                    // sparse along width, slices of depth x height
                    length = width;
                    planeSize = depth * height;
                    if (height != this.image.height || depth != this.image.depth) {
                        throw new Error('Invalid shape: ' + shape.join(', '));
                    }
                } else {
                    throw new Error('Invalid sparse axis: ' + this.segmentation.sparse_axis);
                }
                scanIndices = Array.from({ length }, (_, i) => i);
            }
            for (const scanNr of scanIndices) {
                const start = scanNr * planeSize;
                const end = start + planeSize;
                const slice = (array.data as any).subarray(start, end);
                this.getSegmentationState(scanNr, true, slice);
            }
        } catch (error) {
            console.error('SegmentationItem loadFull failed', error);
        } finally {
            this.loading = false;
        }
    }

    getMask(scanNr: number): Mask | undefined {
        return this.segmentationStates.get(scanNr)?.mask;
    }

    isEmptyForSlice(scanNr: number): boolean {
        const scanIndices = this.segmentation.scan_indices;
        if (Array.isArray(scanIndices) && !scanIndices.includes(scanNr)) {
            return true;
        }
        const state = this.segmentationStates.get(scanNr);
        if (state?.isEmptyForSlice) {
            return true;
        }
        return false;
    }

    getSegmentationState(scanNr: number, create: boolean = false, initialData?: Uint8Array | Uint16Array | Uint32Array | Float32Array): SegmentationState | undefined {
        if (create && !this.segmentationStates.has(scanNr)) {
            const segmentationState = new SegmentationState(this.image, this.segmentation, scanNr, initialData);
            this.segmentationStates.set(scanNr, segmentationState);
        }
        return this.segmentationStates.get(scanNr)!;
    }

    async importOther(scanNr: number, mask: Mask) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        segmentationState.importOther(mask);
    }

    async draw(scanNr: number, drawing: HTMLCanvasElement, settings: PaintSettings) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        await segmentationState.draw(drawing, settings);
    }

    async undo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            segmentationState.undo();
        } else {
            console.warn("SegmentationItem.undo: segmentationState not found", scanNr);
        }
    }

    async redo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            segmentationState.redo();
        } else {
            console.warn("SegmentationItem.redo: segmentationState not found", scanNr);
        }
    }

    //TODO: finish this implementation
    async createEnfaceMask(): Promise<TextureData> {
        if (!this.image.is3D) {
            throw new Error("createEnfaceMask can only be called on 3D images");
        }

        // Wait for segmentation data to load
        if (this.ready) {
            await this.ready;
        }

        const { webgl, width, height, depth } = this.image;
        const { gl } = webgl;

        // Get all slices that have segmentation data
        const scanIndices = this.segmentation.scan_indices ?? Array.from({ length: depth }, (_, i) => i);
        const slicesWithData: number[] = [];

        for (const scanNr of scanIndices) {
            const state = this.segmentationStates.get(scanNr);
            if (state) {
                slicesWithData.push(scanNr);
            }
        }

        if (slicesWithData.length === 0) {
            throw new Error("No segmentation data found for any slices");
        }

        // Create output texture for accumulation (width × depth, R32F)
        // Each horizontal line (y) corresponds to one slice (scanNr)
        const outputTexture = new TextureData(gl, width, depth, 'R32F');

        // Initialize to zero
        outputTexture.clearData();

        // Process each slice - each writes to a different horizontal line in the output
        for (let i = 0; i < slicesWithData.length; i++) {
            const scanNr = slicesWithData[i];
            const state = this.segmentationStates.get(scanNr)!;
            const mask = state.mask;

            // Get the mask texture - ensure it's synced to GPU
            let maskTexture: WebGLTexture;
            if ('textureData' in mask && (mask as any).textureData) {
                // For AbstractDataMask (ProbabilityMask, MultiClassMask, etc.)
                (mask as any).textureData.updateGPU();
                maskTexture = (mask as any).textureData.texture;
            } else if ('texture' in mask && typeof (mask as any).texture !== 'undefined') {
                // For BinaryMask which has a texture getter
                maskTexture = (mask as any).texture;
            } else {
                throw new Error(`Cannot get texture from mask type: ${mask.constructor.name}`);
            }

            // Get bitmask for this mask
            let maskBitmask = 1;
            if ('bitmask' in mask) {
                maskBitmask = (mask as any).bitmask;
            }

            // Create a render target that writes to the specific horizontal line (y = i)
            // The shader will project the mask along height and write to this line
            const lineRenderTarget = {
                framebuffer: outputTexture.renderTarget.framebuffer,
                width: width,
                height: 1, // Single line height
                left: 0,
                bottom: i, // Offset to the correct line (y position)
                attachments: outputTexture.renderTarget.attachments
            };

            const uniforms = {
                u_volume: this.image.texture, // 3D volume texture (may not be used)
                u_mask: maskTexture,
                u_mask_bitmask: maskBitmask,
                height: height // Height dimension to loop over
            };

            // Render this slice's projection to the specific line
            webgl.shaders.enfaceProjectMask.pass(lineRenderTarget, uniforms);
        }

        // Return the R32F texture data
        return outputTexture;
    }

    dispose() {
        // Note: not called currently
        for (const segmentationState of this.segmentationStates.values()) {
            segmentationState.dispose();
        }
        this.segmentationStates.clear();
    }
}
