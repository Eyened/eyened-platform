import { Matrix } from "$lib/matrix";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import { getPrivateEyeRegistrationHeidelberg } from "$lib/registration/privateEyeRegistrationHeidelberg";
import type { InstanceGET } from "../../types/openapi_types";
import { AbstractImage } from "./abstractImage";
import { Image2D } from "./image2D";
import { TextureData } from "./texture";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";
import type { ClaheInput } from "$lib/image-processing/CFImageProcessing";

export class Image3D extends AbstractImage {
    is3D = true;
    is2D = false;
    texture: WebGLTexture;
    
    // Cache for CLAHE-processed slices
    private claheSliceCache = new Map<number, TextureData>();

    constructor(instance: InstanceGET,
        webgl: WebGL,
        img_id: string,
        public readonly data: Uint8Array,
        dimensions: Dimensions,
        meta: any
    ) {
        super(instance, webgl, img_id, dimensions, meta);
        this.texture = initTexture3D(webgl.gl, dimensions, data);
    }

    async createEnfaceProjection(): Promise<Image2D> {
        const { webgl, width, depth, height } = this;

        // Accumulate along z into float texture (R32F)
        const textureData = new TextureData(webgl.gl, width, depth, 'R32F');

        // top and bottom are the top and bottom of the slab (entire volume)
        const top = new TextureData(webgl.gl, width, depth, 'R16UI');
        const bottom = new TextureData(webgl.gl, width, depth, 'R16UI');

        top.uploadData(new Uint16Array(width * depth).fill(0));
        bottom.uploadData(new Uint16Array(width * depth).fill(height));
        
        const uniforms = {
            u_volume: this.texture,
            u_top: top.texture,
            u_bottom: bottom.texture
        };
        textureData.passShader(this.webgl.shaders.enfaceProjection, uniforms);

        // Compute min and max entirely on GPU via progressive 2x2 reductions
        // Returns a 1x1 RG32F texture with min (R) and max (G)
        const minmaxTexture = this.computeMinMaxGPU(textureData);

        // Normalize on GPU to RGBA8
        const normalizedTexture = this.normalizeGPU(textureData, minmaxTexture);
        const proj_img_id = `${this.image_id}_proj`;
        const proj_dimensions = {
            width: this.dimensions.width,
            height: this.dimensions.depth,
            depth: 1,

            width_mm: this.dimensions.width_mm,
            height_mm: this.dimensions.depth_mm,
            depth_mm: -1
        };
        const meta = this.meta;

        const result = new Image2D(this.instance, this.webgl, proj_img_id, normalizedTexture, proj_dimensions, meta);
        this.setOrientation(result);

        textureData.dispose();
        minmaxTexture.dispose();
        top.dispose();
        bottom.dispose();

        return result;
    }

    private setOrientation(result: Image2D) {
        if (this.instance.scan?.mode == 'Vertical 3DSCAN') {
            // rotate 90 degrees around center
            const { width, height } = result.dimensions;
            result.transform = result.transform.rotate(Math.PI / 2, width / 2, height / 2);

            // flip vertically
            const flip = new Matrix(
                1, 0, 0,
                0, -1, 0
            );
            result.transform = flip.multiply(result.transform);
        }

        // Heidelberg normally stores B-scans from bottom to top
        const photoLocators = getPrivateEyeRegistrationHeidelberg(this);
        const allLines = photoLocators.filter(loc => loc instanceof LinePhotoLocator);
        if (allLines.length) {
            const yCoordinates = allLines.map(loc => (loc as LinePhotoLocator).start.y);
            //if they are all decreasing order, flip vertically
            if (yCoordinates.every((v, i, a) => i === 0 || v < a[i - 1])) {
                // flip vertically
                const flip = new Matrix(
                    1, 0, 0,
                    0, -1, 0
                );
                result.transform = flip.multiply(result.transform);
            }
        }
    }

    private computeMinMaxGPU(input: TextureData): TextureData {
        const gl = this.webgl.gl;
        const reduce = this.webgl.shaders.minMaxReduction;

        // Create ping-pong textures for reduction
        let w = input.width;
        let h = input.height;
        
        // Calculate size for first reduction level (maximum size needed)
        const maxW = Math.max(1, Math.floor((w + 1) / 2));
        const maxH = Math.max(1, Math.floor((h + 1) / 2));
        
        // Create both ping and pong textures upfront at maximum size
        let ping = new TextureData(gl, maxW, maxH, 'RG32F');
        let pong = new TextureData(gl, maxW, maxH, 'RG32F');

        // First pass: convert R32F to RG32F (both min and max are the same value)
        const firstUniforms = {
            u_input: input.texture,
            u_srcSize: [w, h],
            u_firstPass: true
        };
        ping.passShader(reduce, firstUniforms);

        // Subsequent passes: ping-pong between textures
        w = maxW;
        h = maxH;
        while (w > 1 || h > 1) {
            const nextW = Math.max(1, Math.floor((w + 1) / 2));
            const nextH = Math.max(1, Math.floor((h + 1) / 2));
            
            const uniforms = {
                u_input: ping.texture,
                u_srcSize: [w, h],
                u_firstPass: false
            };
            pong.passShader(reduce, uniforms);
            
            // Swap ping and pong
            const temp = ping;
            ping = pong;
            pong = temp;
            
            w = nextW;
            h = nextH;
        }

        // Clean up pong (not needed as return value)
        pong.dispose();

        // ping now contains the final 1x1 RG32F texture with min (R) and max (G)
        return ping;
    }

    private normalizeGPU(input: TextureData, minmaxTexture: TextureData): TextureData {
        const gl = this.webgl.gl;
        const outTex = new TextureData(gl, input.width, input.height, 'RGBA');
        const uniforms = {
            u_input: input.texture,
            u_minmax: minmaxTexture.texture
        };
        outTex.passShader(this.webgl.shaders.normalize, uniforms);
        return outTex;
    }

    /**
     * Extract a single slice from the 3D volume as a 2D texture
     * @param index The slice index (0 to depth-1)
     * @returns A TextureData containing the extracted slice in RGBA format
     */
    extractSlice(index: number): TextureData {
        const { webgl, width, height, depth } = this;
        
        // Clamp index to valid range
        const clampedIndex = Math.max(0, Math.min(index, depth - 1));
        
        // Create output texture for the slice
        const sliceTexture = new TextureData(webgl.gl, width, height, 'RGBA');
        
        // Extract the slice using the shader
        const uniforms = {
            u_volume: this.texture,
            u_image_size: [width, height, depth],
            u_index: clampedIndex
        };
        
        sliceTexture.passShader(webgl.shaders.extractSlice, uniforms);
        
        return sliceTexture;
    }

    /**
     * Get CLAHE-processed texture for a specific slice (cached)
     * @param index The slice index (0 to depth-1)
     * @returns A TextureData containing the CLAHE-processed slice, or undefined if processing fails
     */
    async getClaheSliceTexture(index: number): Promise<TextureData | undefined> {
        const { depth } = this;
        const clampedIndex = Math.max(0, Math.min(index, depth - 1));
        
        // Check cache first
        const cached = this.getClaheSliceTextureSync(clampedIndex);
        if (cached) {
            return cached;
        }
        
        // Extract the slice
        const sliceTexture = this.extractSlice(clampedIndex);
        
        // Create a ClaheInput wrapper for the slice
        const claheInput: ClaheInput = {
            width: this.width,
            height: this.height,
            webgl: this.webgl,
            texture: sliceTexture.texture,
            instance: this.instance
        };
        
        // Apply CLAHE processing
        const claheResult = await this.webgl.cfImageProcessing.apply_CLAHE(claheInput);
        
        // Dispose the intermediate slice texture
        sliceTexture.dispose();
        
        // If CLAHE processing succeeded, cache and return the result
        if (claheResult) {
            this.claheSliceCache.set(clampedIndex, claheResult);
            return claheResult;
        }
        
        return undefined;
    }

    getClaheSliceTextureSync(index: number): TextureData | undefined {
        const { depth } = this;
        const clampedIndex = Math.max(0, Math.min(index, depth - 1));
        return this.claheSliceCache.get(clampedIndex);
    }

    dispose(): void {
        // Call parent dispose to clean up segmentations
        super.dispose();
        
        // Dispose all cached CLAHE slice textures
        for (const texture of this.claheSliceCache.values()) {
            texture.dispose();
        }
        this.claheSliceCache.clear();
        
        // Dispose 3D texture
        if (this.texture) {
            this.webgl.gl.deleteTexture(this.texture);
        }
    }
}

function initTexture3D(gl: WebGL2RenderingContext, dimensions: Dimensions, data: Uint8Array): WebGLTexture {

    const texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_3D, texture);

    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);

    gl.texImage3D(
        gl.TEXTURE_3D,
        0,
        gl.R8,
        dimensions.width,
        dimensions.height,
        dimensions.depth,
        0,
        gl.RED,
        gl.UNSIGNED_BYTE,
        data
    );
    return texture;
}
