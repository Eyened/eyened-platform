import { PixelShaderProgram } from '$lib/webgl/FragmentShaderProgram.js';
import type { Image2D } from '$lib/webgl/image2D';
import fs_mirror from './shaders/mirror.frag';
import fs_blur from './shaders/blur.frag';
import fs_contrast_enhance from './shaders/contrast_enhance.frag';
import fs_rgb2lab from './shaders/rgb2lab.frag';
import fs_lab2rgb from './shaders/lab2rgb.frag';
import type { WebGL } from '$lib/webgl/webgl';
import { claheWorker } from './clahe-worker-api';
import { TextureData } from '$lib/webgl/texture';
import fs_standardize from './shaders/standardize.frag';
import fs_lut from './shaders/lut.frag';
export type ceOptions = {
    resolution?: number;
    sigma?: number;
    contrast?: number;
}
type Histogram = { r: Int32Array, g: Int32Array, b: Int32Array };

export class CFImageProcessing {
    mirrorShader: PixelShaderProgram;
    blurShader: PixelShaderProgram;
    ceShader: PixelShaderProgram;
    rgb2labShader: PixelShaderProgram;
    lab2rgbShader: PixelShaderProgram;
    standardizeShader: PixelShaderProgram;
    lutShader: PixelShaderProgram;

    constructor(webgl: WebGL) {
        this.mirrorShader = new PixelShaderProgram(webgl, fs_mirror);
        this.blurShader = new PixelShaderProgram(webgl, fs_blur);
        this.ceShader = new PixelShaderProgram(webgl, fs_contrast_enhance);
        this.rgb2labShader = new PixelShaderProgram(webgl, fs_rgb2lab);
        this.lab2rgbShader = new PixelShaderProgram(webgl, fs_lab2rgb);
        this.standardizeShader = new PixelShaderProgram(webgl, fs_standardize);
        this.lutShader = new PixelShaderProgram(webgl, fs_lut);
    }

    async preprocessAll(image: Image2D) {
        const mirrored = this.mirror(image);
        const blurred = this.blur(image, mirrored);
        const contrastEnhanced = this.runCE(image, false, 4, blurred);
        const sharpened = this.runCE(image, true, 2, blurred);
        const clahe = await this.apply_CLAHE(image);

        const histogram = getHistogram(image);

        const muSigma = this.calculateMuSigma(image, histogram);
        const hist = this.calculateHist(image, histogram);

        return { contrastEnhanced, sharpened, clahe, muSigma, hist };
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
        const ce = new TextureData(webgl.gl, width, height, 'RGBA');
        const uniforms = {
            u_blur: blurred,
            u_sharpen: sharpen,
            u_source: texture,
            u_contrast: contrast,
            u_resolution: [width, height]
        };
        ce.passShader(this.ceShader, uniforms);
        return ce;
    }

    private mirroring(image: Image2D): WebGLTexture {
        const { webgl, width, height, instance: { cfROI } } = image;

        const buffer_mirrored = new TextureData(webgl.gl, width, height, 'RGBA');

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

        buffer_mirrored.passShader(this.mirrorShader, uniforms);
        // TODO: clean up this texture?
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

        const buffer_h = new TextureData(webgl.gl, width, height, 'RGBA');
        const buffer_v = new TextureData(webgl.gl, width, height, 'RGBA');

        const uniformsBlur = {
            u_source: mirrored,
            u_resolution: [width, height],
            u_dir: [0, 1],
            u_kernelSize: kernelSize,
            u_weights: weights
        };

        buffer_h.passShader(this.blurShader, uniformsBlur);
        uniformsBlur.u_dir = [1, 0];
        uniformsBlur.u_source = buffer_h.texture;
        buffer_v.passShader(this.blurShader, uniformsBlur);
        return buffer_v.texture;
    }


    private async apply_CLAHE(image: Image2D): Promise<TextureData | undefined> {
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
        const labTexture = new TextureData(webgl.gl, width, height, 'RGBA');
        labTexture.passShader(this.rgb2labShader, uniforms);
        const labPixels = labTexture.data;

        // apply CLAHE to the L channel
        const l_input = new Uint8ClampedArray(width * height);
        for (let i = 0; i < width * height; i++) {
            l_input[i] = labPixels[i * 4];
        }

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
        labTexture.uploadData(lab_clahe);
        uniforms.u_image = labTexture.texture;
        
        const outputImage = new TextureData(webgl.gl, width, height, 'RGBA');
        outputImage.passShader(this.lab2rgbShader, uniforms);

        labTexture.dispose();
        return outputImage;
    }

    calculateMuSigma(image: Image2D, hist: Histogram): TextureData {
        const result = new TextureData(image.webgl.gl, image.width, image.height, 'RGBA');
                
        const { r, g, b } = hist;
    
        const rStats = calculateMeanAndStd(r);
        const gStats = calculateMeanAndStd(g);
        const bStats = calculateMeanAndStd(b);
    
        const uniforms = {
            u_source: image.texture,
            u_resolution: [image.width, image.height],
            u_mean: [rStats.mean, gStats.mean, bStats.mean],
            u_std: [rStats.std, gStats.std, bStats.std]
        };    
        result.passShader(this.standardizeShader, uniforms);
        return result;
    }

    calculateHist(image: Image2D, hist: Histogram) {
        const result = new TextureData(image.webgl.gl, image.width, image.height, 'RGBA');
    
        const { r, g, b } = hist;
        const [histR, histG, histB] = getTargetHistograms();
    
        const lutR = matchHistogram(r, histR);
        const lutG = matchHistogram(g, histG);
        const lutB = matchHistogram(b, histB);
        const lut = new Float32Array(256 * 3);
    
        for (let i = 0; i < 3 * 256; i += 3) {
            lut[i] = lutR[i / 3] / 255;
            lut[i + 1] = lutG[i / 3] / 255;
            lut[i + 2] = lutB[i / 3] / 255;
        }
    
        const uniforms = {
            u_source: image.texture,
            u_resolution: [image.width, image.height],
            u_lut: lut
        };
    
        result.passShader(this.lutShader, uniforms);
        return result;
    }
}

function calculateMeanAndStd(histogram: Int32Array) {
    const numPixels = histogram.reduce((sum, bin) => sum + bin, 0);
    const mean = histogram.reduce((sum, bin, intensity) => sum + intensity * bin, 0) / numPixels;
    const variance = histogram.reduce((sum, bin, intensity) => sum + bin * ((intensity - mean) ** 2), 0) / numPixels;
    const std = Math.sqrt(variance);
    return { mean, std };
}


function getHistogram(image: Image2D): Histogram {

    const pixels = image.pixels_rgba;

    const r = new Int32Array(256);
    const g = new Int32Array(256);
    const b = new Int32Array(256);


    let center = { x: image.width / 2, y: image.height / 2 };
    let radius = Math.min(center.x, center.y) * 0.95;
    
    let min_x = 0;
    let max_x = image.width;
    let min_y = 0;
    let max_y = image.height;

    const { cfROI } = image.instance;

    try {
        if (cfROI) {
            center = { x: cfROI.center[0], y: cfROI.center[1] };
            radius = cfROI.radius;
            ({ min_x, max_x, min_y, max_y } = cfROI);
        }
    } catch (e) {
        console.warn("Error in cfROI");
    }
    
    const radius_squared = radius * radius;
    for (let y = min_y; y < max_y; y++) {
        for (let x = min_x; x < max_x; x++) {
            const dx = x - center.x;
            const dy = y - center.y;
            const dist_squared = dx * dx + dy * dy;
            if (dist_squared <= radius_squared) {
                const i = 4 * ((y * image.width) + x);
                r[pixels[i]]++;
                g[pixels[i + 1]]++;
                b[pixels[i + 2]]++;
            }
        }
    }

    return { r, g, b }
}

function matchHistogram(sourceCounts: Int32Array, templCounts: Int32Array | number[]): Uint8ClampedArray {
    // https://github.com/scikit-image/scikit-image/blob/main/skimage/exposure/histogram_matching.py#L6

    const tmpl_values = [];
    const tmpl_counts = [];
    for (let i = 0; i < templCounts.length; i++) {
        const v = templCounts[i];
        if (v != 0) {
            // omit values where the count was 0
            tmpl_counts.push(v);
            tmpl_values.push(i);
        }
    }

    const src_quantiles = binsToCDF(sourceCounts);
    const tmpl_quantiles = binsToCDF(new Int32Array(tmpl_counts));

    const lut = [];
    for (let i = 0; i < 256; i++) {
        lut[i] = interp(src_quantiles[i], tmpl_quantiles, new Float32Array(tmpl_values))
    }

    return new Uint8ClampedArray(lut);
}



function cumsum(data: Int32Array): Float32Array {
    const cumulativeSum = [];
    let sum = 0;

    for (const value of data) {
        sum += value;
        cumulativeSum.push(sum);
    }

    return new Float32Array(cumulativeSum);
}

function binsToCDF(data: Int32Array) {
    const cumulative = cumsum(data);
    const sum = cumulative[cumulative.length - 1];
    return cumulative.map((value) => value / sum);
}


function getTargetHistograms() {
    return [[0, 0, 0, 0, 0, 0, 2981, 1659, 1193, 1577, 1322, 1223, 783, 953, 907, 818, 843, 909, 652, 551, 535, 446, 555, 524, 482, 385, 314, 270, 287, 265, 301, 207, 236, 240, 219, 222, 179, 182, 176, 150, 206, 155, 175, 183, 184, 182, 197, 189, 167, 172, 160, 159, 140, 144, 135, 140, 169, 154, 151, 148, 136, 189, 129, 135, 157, 145, 118, 117, 147, 122, 173, 220, 162, 158, 166, 162, 150, 124, 135, 125, 190, 223, 118, 146, 167, 168, 183, 152, 176, 178, 154, 160, 227, 194, 198, 212, 190, 165, 182, 204, 189, 194, 274, 241, 310, 275, 271, 457, 733, 935, 1307, 1789, 2517, 2526, 2359, 2149, 2532, 4368, 4040, 4156, 4718, 5306, 6255, 7008, 7754, 7714, 7087, 7039, 10208, 10038, 10230, 12061, 12391, 11947, 13370, 16092, 14854, 13050, 17464, 23283, 22859, 21840, 21103, 19378, 24921, 23959, 25985, 27940, 31717, 26265, 34442, 38203, 46756, 52906, 36710, 43133, 55922, 53800, 47438, 42472, 51112, 58716, 57270, 52419, 44353, 42452, 44005, 56226, 60840, 51762, 53753, 67388, 59464, 63488, 71947, 69048, 63653, 60029, 59221, 58988, 52436, 47604, 35257, 31614, 32880, 31281, 33034, 25985, 21438, 20881, 19890, 18505, 21453, 19618, 19377, 18451, 17254, 16817, 16020, 17429, 14076, 12447, 13683, 14177, 14717, 13301, 13205, 13838, 11381, 8380, 5404, 2781, 1782, 1078, 719, 628, 531, 403, 318, 269, 256, 219, 112, 31, 14, 10, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [79, 191, 541, 43, 25, 29, 186, 284, 438, 827, 1134, 1130, 855, 918, 1153, 954, 960, 942, 1049, 857, 860, 858, 847, 946, 896, 818, 723, 621, 537, 730, 657, 630, 659, 553, 542, 490, 484, 427, 403, 394, 549, 580, 667, 800, 951, 1148, 1389, 1658, 2225, 3025, 3697, 3913, 3791, 3738, 3848, 6402, 8107, 9201, 11058, 12312, 14507, 17014, 19461, 18262, 14710, 23432, 18524, 16347, 19559, 23978, 25117, 29242, 49808, 55139, 40668, 41906, 41320, 44558, 46467, 52589, 51579, 78238, 69674, 55893, 57775, 65472, 88518, 75092, 54822, 77980, 72577, 57507, 71383, 61275, 43518, 61233, 70405, 52248, 32669, 40989, 34613, 27331, 37955, 36795, 33760, 29024, 20863, 17644, 24940, 25035, 23310, 20909, 21460, 20658, 19854, 12488, 10671, 15334, 16968, 16697, 16221, 14616, 13542, 13040, 18771, 13722, 10441, 7963, 6077, 10285, 8455, 8907, 11531, 7819, 6602, 7413, 11502, 8763, 6796, 6791, 10007, 8016, 10090, 7639, 7090, 9074, 6632, 9094, 7147, 8779, 6534, 6952, 4851, 6020, 5561, 3688, 4367, 3725, 3024, 2094, 2398, 2085, 1557, 1371, 1201, 1065, 838, 633, 799, 617, 613, 571, 545, 485, 468, 603, 514, 569, 595, 521, 545, 457, 514, 452, 486, 407, 491, 465, 353, 252, 273, 193, 211, 222, 239, 245, 222, 163, 119, 109, 90, 41, 29, 9, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [374, 291, 30, 91, 32, 112, 53, 120, 95, 178, 183, 365, 398, 449, 654, 767, 1086, 1165, 1288, 1539, 1310, 1600, 1682, 1724, 1942, 1684, 1629, 1521, 2130, 3112, 3910, 4525, 6090, 8738, 10650, 12826, 12751, 13304, 14776, 18430, 25068, 28779, 35016, 46925, 54890, 57193, 63179, 77344, 88135, 92944, 90092, 86257, 88840, 80698, 72255, 81006, 105896, 110028, 107428, 93180, 82840, 83566, 80226, 67482, 55413, 50092, 42835, 37013, 34666, 34881, 36174, 38601, 41109, 36806, 24495, 22930, 22198, 20156, 17167, 17577, 18891, 21119, 19553, 13404, 12618, 13562, 14223, 12893, 10867, 12295, 12266, 10020, 9390, 10346, 9222, 9505, 9751, 8827, 7561, 7036, 6462, 4713, 5229, 5825, 5354, 3880, 2615, 1879, 1940, 2065, 1754, 1730, 1591, 1613, 1534, 1106, 1044, 1272, 1484, 1369, 1406, 1440, 1395, 1369, 1424, 1440, 1263, 964, 899, 955, 890, 854, 729, 577, 599, 671, 701, 496, 505, 631, 573, 431, 445, 415, 411, 355, 275, 281, 279, 226, 179, 191, 154, 190, 135, 77, 60, 47, 29, 11, 2, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]];
}


function interp(x: number, xp: Float32Array, fp: Float32Array): number {
    const n = xp.length;

    if (n === 0) {
        throw new Error("Arrays xp and fp must not be empty");
    }

    if (n !== fp.length) {
        throw new Error("Arrays xp and fp must have the same length");
    }

    if (x <= xp[0]) {
        return fp[0];
    }

    if (x >= xp[n - 1]) {
        return fp[n - 1];
    }

    let i = 1;
    while (x > xp[i]) {
        i++;
    }

    const xLower = xp[i - 1];
    const xUpper = xp[i];
    const fLower = fp[i - 1];
    const fUpper = fp[i];

    return fLower + ((fUpper - fLower) / (xUpper - xLower)) * (x - xLower);
}

