import type { Instance } from "$lib/datamodel/instance";
import { Matrix } from "$lib/matrix";
import { LinePhotoLocator } from "$lib/registration/photoLocators";
import { getPrivateEyeRegistrationHeidelberg } from "$lib/registration/privateEyeRegistrationHeidelberg";
import { AbstractImage } from "./abstractImage";
import { Image2D } from "./image2D";
import { RenderTexture } from "./renderTexture";
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

    createEnfaceProjection(): Image2D {
        const texture_out = new RenderTexture(this.webgl, this.width, this.depth, 'R32UI', null);
        const rendertarget = texture_out.getRenderTarget();
        const uniforms = {
            u_volumeTexture: this.texture,
            u_height: this.height
        };
        this.webgl.shaders.enfaceProjection.pass(rendertarget, uniforms)
        const sumValues = texture_out.readData();
        texture_out.dispose();

        // CPU implementation for reference (much slower)
        // const sumValues = new Float32Array(this.width * this.depth);
        // for (let x = 0; x < this.width; x++) {
        //     for (let y = 0; y < this.depth; y++) {
        //         let sum = 0;
        //         for (let z = 0; z < this.height; z++) {
        //             const i = x + z * this.width + y * this.width * this.height;
        //             sum += this.data[i];
        //         }
        //         sumValues[x + y * this.width] = sum;
        //     }
        // }


        const { min, max } = sumValues.reduce(
            (acc: { min: number, max: number }, val: number) => ({
                min: Math.min(acc.min, val),
                max: Math.max(acc.max, val),
            }),
            { min: Infinity, max: -Infinity }
        );
        const f = 255 / (max - min);

        const canvas = document.createElement('canvas');
        canvas.width = this.width;
        canvas.height = this.depth;
        const ctx = canvas.getContext('2d')!;

        const imageData = ctx.getImageData(0, 0, this.width, this.depth);
        const img_data = imageData.data;
        for (let i = 0; i < sumValues.length; i++) {
            const g = f * (sumValues[i] - min);
            img_data[4 * i] = g;
            img_data[4 * i + 1] = g;
            img_data[4 * i + 2] = g;
            img_data[4 * i + 3] = 255;
        }
        ctx.putImageData(imageData, 0, 0);

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

        const result = Image2D.fromCanvas(this.instance, webgl, proj_img_id, canvas, proj_dimensions, meta);
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
        return result;
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
