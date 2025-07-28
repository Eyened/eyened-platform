import type { Instance } from "$lib/datamodel/instance.svelte";
import { Matrix } from "$lib/matrix";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import { getPrivateEyeRegistrationHeidelberg } from "$lib/registration/privateEyeRegistrationHeidelberg";
import { AbstractImage } from "./abstractImage";
import { Image2D } from "./image2D";
import { TextureData } from "./texture";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";

export class Image3D extends AbstractImage {
    is3D = true;
    is2D = false;
    texture: WebGLTexture;

    constructor(instance: Instance,
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

        const textureData = new TextureData(webgl.gl, width, depth, 'R32UI');

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

        const normalized = this.normalize(textureData);
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

        const result = Image2D.fromPixelData(this.instance, this.webgl, proj_img_id, normalized, proj_dimensions, meta);
        this.setOrientation(result);

        textureData.dispose();
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

    private normalize(textureData: TextureData): Uint8Array {
        const sumValues = textureData.data as Uint32Array;

        const { min, max } = sumValues.reduce(
            (acc: { min: number; max: number; }, val: number) => ({
                min: Math.min(acc.min, val),
                max: Math.max(acc.max, val),
            }),
            { min: Infinity, max: -Infinity }
        );
        const f = 255 / (max - min);
        const data = new Uint8Array(4 * sumValues.length);
        for (let i = 0; i < sumValues.length; i++) {
            data[4 * i] = f * (sumValues[i] - min);
            data[4 * i + 1] = f * (sumValues[i] - min);
            data[4 * i + 2] = f * (sumValues[i] - min);
            data[4 * i + 3] = 255;
        }
        return data;
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
