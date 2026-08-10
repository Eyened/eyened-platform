import type { ClaheInput } from "$lib/image-processing/CFImageProcessing";
import type { ImageGET } from "../../types/openapi_types";
import { AbstractImage } from "./abstractImage";
import { TextureData } from "./texture";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";

/**
 * Volume stored as a single TEXTURE_2D_ARRAY when slices exceed MAX_3D_TEXTURE_SIZE.
 * Layer size is bounded by MAX_TEXTURE_SIZE; depth by MAX_ARRAY_TEXTURE_LAYERS.
 */
export class ImageSliceStack extends AbstractImage {
    is3D = true;
    is2D = false;

    texture: WebGLTexture;
    private claheSliceCache = new Map<number, TextureData>();

    constructor(
        instance: ImageGET,
        webgl: WebGL,
        img_id: string,
        data: Uint8Array,
        dimensions: Dimensions,
        meta: Record<string, unknown>,
    ) {
        super(instance, webgl, img_id, dimensions, meta);
        this.texture = initTexture2DArray(webgl.gl, dimensions, data);
    }

    /**
     * Extract a single layer as RGBA (grayscale replicated) for CLAHE / 2D paths.
     */
    extractSlice(index: number): TextureData {
        const { webgl, width, height, depth } = this;
        const clampedIndex = Math.max(0, Math.min(Math.round(index), depth - 1));
        const sliceTexture = new TextureData(webgl.gl, width, height, "RGBA");
        sliceTexture.passShader(webgl.shaders.extractSliceArray, {
            u_volume: this.texture,
            u_image_size: [width, height, depth],
            u_index: clampedIndex,
        });
        return sliceTexture;
    }

    async getClaheSliceTexture(
        index: number,
    ): Promise<TextureData | undefined> {
        const clampedIndex = Math.max(0, Math.min(Math.round(index), this.depth - 1));

        const cached = this.getClaheSliceTextureSync(clampedIndex);
        if (cached) {
            return cached;
        }

        const sliceTexture = this.extractSlice(clampedIndex);
        const claheInput: ClaheInput = {
            width: this.width,
            height: this.height,
            webgl: this.webgl,
            texture: sliceTexture.texture,
            instance: this.instance,
        };

        const claheResult =
            await this.webgl.cfImageProcessing.apply_CLAHE(claheInput);

        sliceTexture.dispose();

        if (claheResult) {
            this.claheSliceCache.set(clampedIndex, claheResult);
            return claheResult;
        }

        return undefined;
    }

    getClaheSliceTextureSync(index: number): TextureData | undefined {
        const clampedIndex = Math.max(0, Math.min(Math.round(index), this.depth - 1));
        return this.claheSliceCache.get(clampedIndex);
    }

    dispose(): void {
        super.dispose();

        for (const texture of this.claheSliceCache.values()) {
            texture.dispose();
        }
        this.claheSliceCache.clear();

        if (this.texture) {
            this.webgl.gl.deleteTexture(this.texture);
        }
    }
}

function initTexture2DArray(
    gl: WebGL2RenderingContext,
    dimensions: Dimensions,
    data: Uint8Array,
): WebGLTexture {
    const { width, height, depth } = dimensions;
    const expectedSize = width * height * depth;
    if (data.length < expectedSize) {
        throw new Error(
            `Volume data length ${data.length} is smaller than ` +
                `${width}x${height}x${depth} (${expectedSize})`,
        );
    }

    const texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D_ARRAY, texture);

    gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    // Prefer exact-sized view when padded trailing bytes exist (texImage3D would tolerate them).
    const payload =
        data.length === expectedSize ? data : data.subarray(0, expectedSize);

    gl.texImage3D(
        gl.TEXTURE_2D_ARRAY,
        0,
        gl.R8,
        width,
        height,
        depth,
        0,
        gl.RED,
        gl.UNSIGNED_BYTE,
        payload,
    );
    return texture;
}
