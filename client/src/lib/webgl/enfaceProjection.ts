import { SIMPLE_ENFACE_FEATURE_INDEX } from "$lib/viewer-window/enfaceProjectionKeys";
import type { Mask } from "./mask.svelte";
import {
    BinaryMask,
    MultiClassMask,
    MultiLabelMask,
    ProbabilityMask,
    QuestionableMask,
} from "./mask.svelte";
import type { Shaders } from "./shaders";
import { tagFramebuffer, TextureData } from "./texture";
import type { RenderTarget } from "./types";
import type { SegmentationState } from "./segmentationState.svelte";
import type { SegmentationItem } from "./segmentationItem.svelte";

function lineRenderTarget(
    framebuffer: WebGLFramebuffer,
    width: number,
    scanNr: number,
    gl: WebGL2RenderingContext,
): RenderTarget {
    return {
        framebuffer,
        width,
        height: 1,
        left: 0,
        bottom: scanNr,
        attachments: [gl.COLOR_ATTACHMENT0],
    };
}

function syncMaskToGpu(mask: Mask): void {
    if (mask instanceof BinaryMask || mask instanceof QuestionableMask) {
        void mask.bitMaskTexture.texture;
    } else if (mask instanceof ProbabilityMask) {
        void mask.textureData.texture;
    } else if (mask instanceof MultiClassMask || mask instanceof MultiLabelMask) {
        void mask.textureData.texture;
    }
}

function getBinaryMaskSource(mask: Mask): {
    texture: WebGLTexture;
    bitmask: number;
} {
    if (mask instanceof BinaryMask || mask instanceof QuestionableMask) {
        syncMaskToGpu(mask);
        return {
            texture: mask.bitMaskTexture.texture,
            bitmask: mask.bitMaskTexture.bitmask,
        };
    }
    throw new Error(
        `Expected binary mask for enface projection, got ${mask.constructor.name}`,
    );
}

function getProbabilityMaskTexture(mask: Mask): WebGLTexture {
    if (mask instanceof ProbabilityMask) {
        syncMaskToGpu(mask);
        return mask.textureData.texture;
    }
    throw new Error(
        `Expected probability mask for enface projection, got ${mask.constructor.name}`,
    );
}

function getMultiMaskTexture(mask: Mask): WebGLTexture {
    if (mask instanceof MultiClassMask || mask instanceof MultiLabelMask) {
        syncMaskToGpu(mask);
        return mask.textureData.texture;
    }
    throw new Error(
        `Expected multi-feature mask for enface projection, got ${mask.constructor.name}`,
    );
}

export class EnfaceProjection {
    /** Normalized thickness map (R8): one value per enface pixel. */
    readonly textureData: TextureData;
    private readonly framebuffer: WebGLFramebuffer;
    private readonly shaders: Shaders;
    private readonly gl: WebGL2RenderingContext;
    private maxThicknessCache = 1;
    private maxThicknessDirty = true;

    constructor(
        gl: WebGL2RenderingContext,
        shaders: Shaders,
        public readonly width: number,
        public readonly depth: number,
    ) {
        this.gl = gl;
        this.shaders = shaders;
        this.textureData = new TextureData(gl, width, depth, "R8");
        this.textureData.clearData();

        this.framebuffer = gl.createFramebuffer()!;
        tagFramebuffer(gl, this.framebuffer);
        this.attachFramebuffer();
    }

    private attachFramebuffer(): void {
        const gl = this.gl;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.framebufferTexture2D(
            gl.FRAMEBUFFER,
            gl.COLOR_ATTACHMENT0,
            gl.TEXTURE_2D,
            this.textureData.texture,
            0,
        );
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }

    projectSlice(scanNr: number, mask: Mask, bscanHeight: number): void {
        this.projectSliceForFeature(
            scanNr,
            mask,
            SIMPLE_ENFACE_FEATURE_INDEX,
            bscanHeight,
        );
    }

    projectSliceForFeature(
        scanNr: number,
        mask: Mask,
        featureIndex: number,
        bscanHeight: number,
    ): void {
        if (scanNr < 0 || scanNr >= this.depth) {
            return;
        }

        syncMaskToGpu(mask);
        this.attachFramebuffer();

        const renderTarget = lineRenderTarget(
            this.framebuffer,
            this.width,
            scanNr,
            this.gl,
        );

        const invHeight = 1 / bscanHeight;
        const representation = mask.segmentation.data_representation;

        if (representation === "Probability") {
            this.shaders.enfaceProjectProbability.pass(renderTarget, {
                u_mask: getProbabilityMaskTexture(mask),
                height: bscanHeight,
                u_inv_height: invHeight,
            });
        } else if (
            representation === "Binary" ||
            representation === "DualBitMask"
        ) {
            const { texture, bitmask } = getBinaryMaskSource(mask);
            this.shaders.enfaceProjectBinary.pass(renderTarget, {
                u_mask: texture,
                u_mask_bitmask: bitmask,
                height: bscanHeight,
                u_inv_height: invHeight,
            });
        } else if (representation === "MultiClass") {
            this.shaders.enfaceProjectMultiClass.pass(renderTarget, {
                u_mask: getMultiMaskTexture(mask),
                u_feature_index: featureIndex,
                height: bscanHeight,
                u_inv_height: invHeight,
            });
        } else if (representation === "MultiLabel") {
            this.shaders.enfaceProjectMultiLabel.pass(renderTarget, {
                u_mask: getMultiMaskTexture(mask),
                u_feature_bitmask: 1 << (featureIndex - 1),
                height: bscanHeight,
                u_inv_height: invHeight,
            });
        }

        this.textureData.markCPUDirty();
        this.invalidateMaxThickness();
    }

    projectAll(
        segmentationItem: SegmentationItem,
        bscanHeight: number,
    ): void {
        this.projectAllLayers(
            segmentationItem,
            SIMPLE_ENFACE_FEATURE_INDEX,
            bscanHeight,
        );
    }

    projectAllLayers(
        segmentationItem: SegmentationItem,
        featureIndex: number,
        bscanHeight: number,
    ): void {
        this.clearAll();
        for (const [scanNr, state] of segmentationItem.segmentationStates) {
            this.projectSliceForFeature(
                scanNr,
                state.mask,
                featureIndex,
                bscanHeight,
            );
        }
    }

    clearSlice(scanNr: number): void {
        if (scanNr < 0 || scanNr >= this.depth) {
            return;
        }

        this.attachFramebuffer();
        const gl = this.gl;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.viewport(0, scanNr, this.width, 1);
        gl.scissor(0, scanNr, this.width, 1);
        gl.disable(gl.BLEND);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        this.textureData.markCPUDirty();
        this.invalidateMaxThickness();
    }

    clearAll(): void {
        this.textureData.clearData();
        this.invalidateMaxThickness();
    }

    /** Max normalized thickness in [0, 1] for heatmap scaling. */
    getMaxThickness(): number {
        if (!this.maxThicknessDirty) {
            return this.maxThicknessCache;
        }

        const data = this.textureData.data as Uint8Array;
        let max = 0;
        for (let i = 0; i < data.length; i++) {
            if (data[i] > max) {
                max = data[i];
            }
        }

        // Values are normalized thickness in [0, 1] (stored as 0–255).
        this.maxThicknessCache = Math.max(1 / 255, max / 255);
        this.maxThicknessDirty = false;
        return this.maxThicknessCache;
    }

    private invalidateMaxThickness(): void {
        this.maxThicknessDirty = true;
    }

    dispose(): void {
        this.gl.deleteFramebuffer(this.framebuffer);
        this.textureData.dispose();
    }
}

export function projectSegmentationStates(
    projection: EnfaceProjection,
    states: Iterable<[number, SegmentationState]>,
    bscanHeight: number,
): void {
    for (const [scanNr, state] of states) {
        projection.projectSlice(scanNr, state.mask, bscanHeight);
    }
}
