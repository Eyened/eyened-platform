import type { Mask } from "./mask.svelte";
import { BinaryMask, ProbabilityMask, QuestionableMask } from "./mask.svelte";
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

export class EnfaceProjection {
    readonly textureData: TextureData;
    private readonly framebuffer: WebGLFramebuffer;
    private readonly shaders: Shaders;
    private readonly gl: WebGL2RenderingContext;

    constructor(
        gl: WebGL2RenderingContext,
        shaders: Shaders,
        public readonly width: number,
        public readonly depth: number,
    ) {
        this.gl = gl;
        this.shaders = shaders;
        this.textureData = new TextureData(gl, width, depth, "R32F");
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

        const representation = mask.segmentation.data_representation;
        if (representation === "Probability") {
            this.shaders.enfaceProjectProbability.pass(renderTarget, {
                u_mask: getProbabilityMaskTexture(mask),
                height: bscanHeight,
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
            });
        }

        this.textureData.markCPUDirty();
    }

    projectAll(
        segmentationItem: SegmentationItem,
        bscanHeight: number,
    ): void {
        this.clearAll();
        for (const [scanNr, state] of segmentationItem.segmentationStates) {
            this.projectSlice(scanNr, state.mask, bscanHeight);
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
    }

    clearAll(): void {
        this.textureData.clearData();
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
