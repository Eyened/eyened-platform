import type { Instance } from "$lib/datamodel/instance.svelte";
import { Matrix } from "$lib/matrix";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import { getPrivateEyeRegistrationHeidelberg } from "$lib/registration/privateEyeRegistrationHeidelberg";
import { AbstractImage } from "./abstractImage";
import { Image2D } from "./image2D";
import { RenderTexture } from "./renderTexture";
import { TextureData } from "./texture";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";

export class Image3D extends AbstractImage {
    is3D = true;
    is2D = false;

    constructor(instance: Instance,
        webgl: WebGL,
        img_id: string,

        public readonly data: Uint8Array,
        dimensions: Dimensions,
        meta: any
    ) {
        super(instance, webgl, img_id, dimensions, meta, initTexture(webgl.gl, dimensions, data));
    }

    async createEnfaceProjection(): Promise<Image2D> {
        const textureData = new TextureData(this.webgl.gl, this.width, this.depth, 'R32UI');

        const top = new TextureData(this.webgl.gl, this.width, this.depth, 'R16UI');
        const bottom = new TextureData(this.webgl.gl, this.width, this.depth, 'R16UI');

        top.uploadData(new Uint16Array(this.width * this.depth).fill(0));
        bottom.uploadData(new Uint16Array(this.width * this.depth).fill(this.height));

        const uniforms = {
            u_volume: this.texture,
            u_top: top.texture,
            u_bottom: bottom.texture
        };
        textureData.passShader(this.webgl.shaders.enfaceProjection, uniforms);

        const bitmap = await this.normalize(textureData);

        const webgl = this.webgl;
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

        const result = Image2D.fromBitmap(this.instance, webgl, proj_img_id, bitmap, proj_dimensions, meta);

        this.setOrientation(result);
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

    private async normalize(textureData: TextureData): Promise<ImageBitmap> {
        const sumValues = textureData.data as Uint32Array;

        const { min, max } = sumValues.reduce(
            (acc: { min: number; max: number; }, val: number) => ({
                min: Math.min(acc.min, val),
                max: Math.max(acc.max, val),
            }),
            { min: Infinity, max: -Infinity }
        );
        const f = 255 / (max - min);
        const imageData = new ImageData(this.width, this.depth);
        const img_data = imageData.data;
        for (let i = 0; i < sumValues.length; i++) {
            const g = f * (sumValues[i] - min);
            img_data[4 * i] = g;
            img_data[4 * i + 1] = g;
            img_data[4 * i + 2] = g;
            img_data[4 * i + 3] = 255;
        }
        const bitmap = await createImageBitmap(imageData);
        return bitmap;
    }
}

function initTexture(gl: WebGL2RenderingContext, dimensions: Dimensions, data: Uint8Array): WebGLTexture {

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
