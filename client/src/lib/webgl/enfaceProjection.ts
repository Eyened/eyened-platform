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
    } else if (
        mask instanceof MultiClassMask ||
        mask instanceof MultiLabelMask
    ) {
        void mask.textureData.texture;
    }
}

type MaskProjectionUniforms =
    | { shader: "binary"; u_mask: WebGLTexture; u_mask_bitmask: number }
    | { shader: "probability"; u_mask: WebGLTexture }
    | { shader: "multiclass"; u_mask: WebGLTexture; u_feature_index: number }
    | { shader: "multilabel"; u_mask: WebGLTexture; u_feature_bitmask: number };

function getMaskProjectionUniforms(
    mask: Mask,
    featureIndex: number,
): MaskProjectionUniforms {
    syncMaskToGpu(mask);
    const rep = mask.segmentation.data_representation;

    if (rep === "Probability" && mask instanceof ProbabilityMask) {
        return { shader: "probability", u_mask: mask.textureData.texture };
    }
    if (
        (rep === "Binary" || rep === "DualBitMask") &&
        (mask instanceof BinaryMask || mask instanceof QuestionableMask)
    ) {
        return {
            shader: "binary",
            u_mask: mask.bitMaskTexture.texture,
            u_mask_bitmask: mask.bitMaskTexture.bitmask,
        };
    }
    if (
        (rep === "MultiClass" || rep === "MultiLabel") &&
        (mask instanceof MultiClassMask || mask instanceof MultiLabelMask)
    ) {
        const u_mask = mask.textureData.texture;
        if (rep === "MultiClass") {
            return {
                shader: "multiclass",
                u_mask,
                u_feature_index: featureIndex,
            };
        }
        return {
            shader: "multilabel",
            u_mask,
            u_feature_bitmask: 1 << (featureIndex - 1),
        };
    }
    throw new Error(
        `Unsupported mask for enface projection: ${mask.constructor.name} / ${rep}`,
    );
}

export class EnfaceProjection {
    /** Normalized thickness map (R8): one value per enface pixel. */
    readonly textureData: TextureData;
    private readonly framebuffer: WebGLFramebuffer;
    private readonly shaders: Shaders;
    private readonly gl: WebGL2RenderingContext;
    private thicknessRangeCache = { min: 0, max: 1 };
    private thicknessRangeDirty = true;

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

    projectSliceForFeature(
        scanNr: number,
        mask: Mask,
        featureIndex: number,
        bscanHeight: number,
    ): void {
        if (scanNr < 0 || scanNr >= this.depth) {
            return;
        }

        const renderTarget = lineRenderTarget(
            this.framebuffer,
            this.width,
            scanNr,
            this.gl,
        );

        const base = {
            height: bscanHeight,
            u_inv_height: 1 / bscanHeight,
        };
        const uniforms = getMaskProjectionUniforms(mask, featureIndex);

        switch (uniforms.shader) {
            case "binary":
                this.shaders.enfaceProjectBinary.pass(renderTarget, {
                    ...base,
                    u_mask: uniforms.u_mask,
                    u_mask_bitmask: uniforms.u_mask_bitmask,
                });
                break;
            case "probability":
                this.shaders.enfaceProjectProbability.pass(renderTarget, {
                    ...base,
                    u_mask: uniforms.u_mask,
                });
                break;
            case "multiclass":
                this.shaders.enfaceProjectMultiClass.pass(renderTarget, {
                    ...base,
                    u_mask: uniforms.u_mask,
                    u_feature_index: uniforms.u_feature_index,
                });
                break;
            case "multilabel":
                this.shaders.enfaceProjectMultiLabel.pass(renderTarget, {
                    ...base,
                    u_mask: uniforms.u_mask,
                    u_feature_bitmask: uniforms.u_feature_bitmask,
                });
                break;
        }

        this.textureData.markGPUCurrent();
        this.invalidateThicknessRange();
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

        const gl = this.gl;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.viewport(0, scanNr, this.width, 1);
        gl.scissor(0, scanNr, this.width, 1);
        gl.disable(gl.BLEND);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        this.textureData.markGPUCurrent();
        this.invalidateThicknessRange();
    }

    clearAll(): void {
        const gl = this.gl;
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
        gl.viewport(0, 0, this.width, this.depth);
        gl.scissor(0, 0, this.width, this.depth);
        gl.disable(gl.BLEND);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        this.textureData.markGPUCurrent();
        this.invalidateThicknessRange();
    }

    /** Min/max normalized thickness among foreground pixels, for heatmap scaling. */
    getThicknessRange(): { min: number; max: number } {
        if (!this.thicknessRangeDirty) {
            return this.thicknessRangeCache;
        }

        const data = this.textureData.data as Uint8Array;
        let min = 255;
        let max = 0;
        for (let i = 0; i < data.length; i++) {
            const value = data[i];
            if (value === 0) {
                continue;
            }
            if (value < min) {
                min = value;
            }
            if (value > max) {
                max = value;
            }
        }

        // Values are normalized thickness in [0, 1] (stored as 0–255).
        if (max === 0) {
            this.thicknessRangeCache = { min: 0, max: 1 / 255 };
        } else {
            this.thicknessRangeCache = { min: min / 255, max: max / 255 };
        }
        this.thicknessRangeDirty = false;
        return this.thicknessRangeCache;
    }

    private invalidateThicknessRange(): void {
        this.thicknessRangeDirty = true;
    }

    dispose(): void {
        this.gl.deleteFramebuffer(this.framebuffer);
        this.textureData.dispose();
    }
}
