import type { ClaheInput } from "$lib/image-processing/CFImageProcessing";
import type { ImageGET } from "../../types/openapi_types";
import { AbstractImage } from "./abstractImage";
import { TextureData } from "./texture";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";
import { assertSliceStackFits, getVolumeLimits } from "./volumeLimits";

export class ImageSliceStack extends AbstractImage {
    is3D = true;
    is2D = false;
    isSliceStack = true;

    private readonly slices: TextureData[];
    private claheSliceCache = new Map<number, TextureData>();
    private activeSliceIndex = 0;

    constructor(
        instance: ImageGET,
        webgl: WebGL,
        img_id: string,
        data: Uint8Array,
        dimensions: Dimensions,
        meta: any,
    ) {
        super(instance, webgl, img_id, dimensions, meta);
        assertSliceStackFits(dimensions, getVolumeLimits(webgl.gl));
        this.slices = initSliceTextures(
            webgl.gl,
            dimensions.width,
            dimensions.height,
            dimensions.depth,
            data,
        );
    }

    /** Active slice texture; updated by the renderer via {@link setActiveSliceIndex}. */
    get texture(): WebGLTexture {
        return this.getSliceTexture(this.activeSliceIndex);
    }

    setActiveSliceIndex(index: number): void {
        this.activeSliceIndex = Math.max(
            0,
            Math.min(index, this.depth - 1),
        );
    }

    getSlice(index: number): TextureData {
        const clampedIndex = Math.max(0, Math.min(index, this.depth - 1));
        return this.slices[clampedIndex];
    }

    getSliceTexture(index: number): WebGLTexture {
        return this.getSlice(index).texture;
    }

    async getClaheSliceTexture(
        index: number,
    ): Promise<TextureData | undefined> {
        const clampedIndex = Math.max(0, Math.min(index, this.depth - 1));

        const cached = this.getClaheSliceTextureSync(clampedIndex);
        if (cached) {
            return cached;
        }

        const slice = this.getSlice(clampedIndex);
        const claheInput: ClaheInput = {
            width: this.width,
            height: this.height,
            webgl: this.webgl,
            texture: slice.texture,
            instance: this.instance,
        };

        const claheResult =
            await this.webgl.cfImageProcessing.apply_CLAHE(claheInput);

        if (claheResult) {
            this.claheSliceCache.set(clampedIndex, claheResult);
            return claheResult;
        }

        return undefined;
    }

    getClaheSliceTextureSync(index: number): TextureData | undefined {
        const clampedIndex = Math.max(0, Math.min(index, this.depth - 1));
        return this.claheSliceCache.get(clampedIndex);
    }

    dispose(): void {
        super.dispose();

        for (const texture of this.claheSliceCache.values()) {
            texture.dispose();
        }
        this.claheSliceCache.clear();

        for (const slice of this.slices) {
            slice.dispose();
        }
    }
}

function initSliceTextures(
    gl: WebGL2RenderingContext,
    width: number,
    height: number,
    depth: number,
    data: Uint8Array,
): TextureData[] {
    const sliceSize = width * height;
    const expectedSize = sliceSize * depth;
    if (data.length !== expectedSize) {
        throw new Error(
            `Volume data length ${data.length} does not match ` +
                `${width}x${height}x${depth} (${expectedSize})`,
        );
    }

    const slices: TextureData[] = [];
    for (let i = 0; i < depth; i++) {
        const slice = new TextureData(gl, width, height, "R8");
        slice.uploadData(data.subarray(i * sliceSize, (i + 1) * sliceSize));
        slices.push(slice);
    }
    return slices;
}
