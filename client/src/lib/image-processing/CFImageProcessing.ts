import { PixelShaderProgram } from '$lib/webgl/FragmentShaderProgram.js';
import type { Image2D } from '$lib/webgl/image2D';
import { RenderTexture } from '$lib/webgl/renderTexture';
import fs_mirror from './shaders/mirror.frag';
import fs_blur from './shaders/blur.frag';
import fs_contrast_enhance from './shaders/contrast_enhance.frag';
import fs_rgb2lab from './shaders/rgb2lab.frag';
import fs_lab2rgb from './shaders/lab2rgb.frag';
import type { WebGL } from '$lib/webgl/webgl';
import { CLAHE } from './CLAHE';
import { claheWorker } from './clahe-worker-api';

export type ceOptions = {
    resolution?: number;
    sigma?: number;
    contrast?: number;
}


export class CFImageProcessing {
    mirrorShader: PixelShaderProgram;
    blurShader: PixelShaderProgram;
    ceShader: PixelShaderProgram;
    rgb2labShader: PixelShaderProgram;
    lab2rgbShader: PixelShaderProgram;

    constructor(private readonly webgl: WebGL) {
        this.mirrorShader = new PixelShaderProgram(webgl, fs_mirror);
        this.blurShader = new PixelShaderProgram(webgl, fs_blur);
        this.ceShader = new PixelShaderProgram(webgl, fs_contrast_enhance);
        this.rgb2labShader = new PixelShaderProgram(webgl, fs_rgb2lab);
        this.lab2rgbShader = new PixelShaderProgram(webgl, fs_lab2rgb);
    }

    async preprocessAll(image: Image2D) {
        const mirrored = this.mirror(image);
        const blurred = this.blur(image, mirrored);
        const contrastEnhanced = this.runCE(image, false, 4, blurred);
        const sharpened = this.runCE(image, true, 2, blurred);
        const clahe = await this.apply_CLAHE(image);

        return { contrastEnhanced, sharpened, clahe };
    }

    private mirror(image: Image2D): WebGLTexture {
        const { instance: cfROI } = image;
        if (cfROI) {
            return this.mirroring(image);
        }
        // If no ROI, return the original image
        return image.texture;
    }


    private runCE(image: Image2D, sharpen: boolean, contrast: number, blurred: WebGLTexture) {
        const { width, height, texture, webgl } = image;

        const ce = new RenderTexture(webgl, width, height, 'RGBA', null);
        const uniforms = {
            u_blur: blurred,
            u_sharpen: sharpen,
            u_source: texture,
            u_contrast: contrast,
            u_resolution: [width, height]
        };

        this.ceShader.pass(ce.getRenderTarget(), uniforms);
        return ce;
    }

    private mirroring(image: Image2D): WebGLTexture {
        const { webgl, width, height, instance: { cfROI } } = image;

        const buffer_mirrored = new RenderTexture(webgl, width, height, 'RGBA', null);

        let cx = width / 2;
        let cy = height / 2;
        let radius = Math.min(width, height) / 2;

        type LineCoords = [[number, number], [number, number]];
        type Lines = {
            top?: LineCoords;
            bottom?: LineCoords;
            left?: LineCoords;
            right?: LineCoords;
        }
        let lines: Lines = {};
        try {
            if (cfROI) {
                ({ center: [cx, cy], radius, lines } = cfROI);
            }
        } catch (e) {
            console.warn('Error in cfROI', e);
        }
        let [min_x, min_y] = [0, 0];
        let [max_x, max_y] = [width, height];

        let x0, y0, x1, y1;
        if (lines.top) {
            ([[x0, y0], [x1, y1]] = lines.top);
            min_y = Math.max(min_y, y0);
            min_y = Math.max(min_y, y1);
        }
        if (lines.bottom) {
            ([[x0, y0], [x1, y1]] = lines.bottom);
            max_y = Math.min(max_y, y0);
            max_y = Math.min(max_y, y1);
        }
        if (lines.left) {
            ([[x0, y0], [x1, y1]] = lines.left);
            min_x = Math.max(min_x, x0);
            min_x = Math.max(min_x, x1);
        }
        if (lines.right) {
            ([[x0, y0], [x1, y1]] = lines.right);
            max_x = Math.min(max_x, x0);
            max_x = Math.min(max_x, x1);
        }

        const uniforms = {
            u_source: image.texture,
            u_resolution: [width, height],
            u_ROIrect: [min_x, min_y, max_x, max_y],
            u_ROIcircle: [cx, cy, radius],
        }

        this.mirrorShader.pass(buffer_mirrored.getRenderTarget(), uniforms);
        return buffer_mirrored.texture;
    }


    private blur(image: Image2D, mirrored: WebGLTexture): WebGLTexture {
        const { width, height, webgl, instance: { cfROI } } = image;
        let sigma = 0.025 * Math.min(width, height);
        if (cfROI) {
            sigma = 0.05 * cfROI.radius;
        }
        let kernelSize = Math.ceil(sigma * 3);
        kernelSize = Math.min(kernelSize, 256);
        const weights = new Float32Array(kernelSize);
        let sum = 0;
        for (let x = 0; x < kernelSize; x++) {
            weights[x] = Math.exp(-0.5 * x * x / (sigma * sigma));
            if (x === 0) { // center
                sum += weights[x];
            } else { // sides
                sum += 2 * weights[x];
            }
        }
        for (let i = 0; i < kernelSize; i++) {
            weights[i] /= sum;
        }

        const buffer_h = new RenderTexture(webgl, width, height, 'RGBA', null);
        const buffer_v = new RenderTexture(webgl, width, height, 'RGBA', null);

        const uniformsBlur = {
            u_source: mirrored,
            u_resolution: [width, height],
            u_dir: [0, 1],
            u_kernelSize: kernelSize,
            u_weights: weights
        };

        this.blurShader.pass(buffer_h.getRenderTarget(), uniformsBlur);
        uniformsBlur.u_dir = [1, 0];
        uniformsBlur.u_source = buffer_h.texture;
        this.blurShader.pass(buffer_v.getRenderTarget(), uniformsBlur);
        return buffer_v.texture;
    }


    private async apply_CLAHE(image: Image2D): Promise<RenderTexture | undefined> {
        const { width, height, webgl, texture, instance: { cfROI } } = image;

        // CLAHE tile size
        // adapted to the image size
        let tileSize = Math.floor(Math.min(width, height) / 64);
        if (cfROI) {
            tileSize = Math.floor(cfROI.radius / 32);
        }
        if (tileSize == 0) {
            return undefined;
        }




        // convert image to LAB
        const uniforms = {
            u_image: texture,
            u_resolution: [width, height]
        }
        const labTexture = new RenderTexture(webgl, width, height, 'RGBA', null);
        webgl.cfImageProcessing.rgb2labShader.pass(labTexture.getRenderTarget(), uniforms);
        const labPixels = labTexture.readData();

        // apply CLAHE to the L channel
        const l_input = new Uint8ClampedArray(width * height);
        for (let i = 0; i < width * height; i++) {
            l_input[i] = labPixels[i * 4];
        }

        // const c = new CLAHE(tileSize);
        // const l_output = c.applyClahe(l_input, width, height);

        const l_output = await claheWorker.processClahe(l_input, width, height,
            { tileSize }
        );

        // create LAB image with CLAHE applied
        const lab_clahe = new Uint8Array(width * height * 4);
        for (let i = 0; i < width * height; i++) {
            const idx = i * 4;
            lab_clahe[idx] = l_output[i];
            lab_clahe[idx + 1] = labPixels[idx + 1];
            lab_clahe[idx + 2] = labPixels[idx + 2];
            lab_clahe[idx + 3] = 255;
        }

        // convert LAB back to RGB
        labTexture.setDataArray(lab_clahe);
        uniforms.u_image = labTexture.texture;
        const outputImage = new RenderTexture(webgl, width, height, 'RGBA', null);
        webgl.cfImageProcessing.lab2rgbShader.pass(outputImage.getRenderTarget(), uniforms);

        return outputImage;
    }
}