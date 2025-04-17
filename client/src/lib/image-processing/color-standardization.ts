import { PixelShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { Image2D } from "$lib/webgl/image2D";
import { RenderTexture } from "$lib/webgl/renderTexture";


type Histogram = { r: Int32Array, g: Int32Array, b: Int32Array };

export function colorStandardization(image: Image2D): { muSigma: RenderTexture, hist: RenderTexture } {

    const histogram = getHistogram(image);

    const muSigma = calculateMuSigma(image, histogram);
    const hist = calculateHist(image, histogram);

    return { muSigma, hist };
}

function calculateMuSigma(image: Image2D, hist: Histogram) {
    const result = new RenderTexture(image.webgl, image.width, image.height, 'RGBA', null);
    const shader = new PixelShaderProgram(image.webgl, fs_standardize);
    const renderTarget = result.getRenderTarget();
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

    shader.pass(renderTarget, uniforms);
    return result;
}

function calculateHist(image: Image2D, hist: Histogram) {
    const result = new RenderTexture(image.webgl, image.width, image.height, 'RGBA', null);

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

    const shader = new PixelShaderProgram(image.webgl, fs_lut);

    const renderTarget = result.getRenderTarget()
    const uniforms = {
        u_source: image.texture,
        u_resolution: [image.width, image.height],
        u_lut: lut
    };

    shader.pass(renderTarget, uniforms);
    return result;
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
    // this are the r/g/b bincounts from a reference image with proper contrast/brightness
    // return [
    //     [0, 0, 1, 1, 7, 3, 2, 0, 1, 4, 1, 2, 0, 3, 1, 2, 0, 1, 2, 0, 1, 0, 1, 0, 1, 1, 2, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 2, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 3, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 0, 2, 1, 1, 1, 2, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 3, 5, 11, 18, 29, 71, 105, 122, 145, 185, 215, 263, 408, 476, 445, 645, 1017, 1332, 1681, 2029, 2401, 3533, 3419, 3701, 3980, 5122, 4453, 6396, 7971, 10634, 13659, 10808, 14541, 19723, 19958, 18724, 17668, 22057, 25591, 25917, 25400, 23544, 24559, 25448, 32204, 35694, 28449, 28937, 33161, 29968, 31387, 38103, 37041, 36779, 36937, 38089, 40882, 39767, 41746, 33746, 33281, 36340, 34861, 39684, 33190, 29794, 30265, 31220, 28941, 34305, 30760, 32407, 33324, 31549, 31540, 28748, 32064, 28672, 26380, 28818, 27659, 26358, 20916, 19734, 21266, 21173, 18900, 14760, 11106, 9731, 6740, 4102, 3007, 2026, 1344, 939, 607, 555, 498, 328, 316, 140, 65, 28, 7, 7, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    //     [0, 0, 0, 4, 0, 3, 0, 3, 1, 3, 1, 0, 1, 2, 3, 0, 0, 1, 6, 0, 0, 0, 3, 2, 2, 1, 0, 1, 4, 3, 2, 3, 1, 0, 1, 1, 1, 1, 0, 0, 0, 2, 0, 0, 5, 5, 4, 17, 43, 54, 79, 86, 106, 140, 172, 297, 484, 577, 703, 818, 997, 1301, 1870, 2091, 1549, 2740, 2280, 2199, 2479, 3284, 3680, 4720, 8608, 11864, 9419, 10219, 10511, 11858, 12934, 14998, 14731, 22610, 21214, 17267, 18260, 21669, 31693, 28701, 22391, 34486, 32970, 27762, 35997, 31691, 23594, 35656, 43890, 35225, 24796, 33327, 29738, 24672, 35972, 38774, 36327, 32741, 24750, 21037, 30576, 33575, 33239, 31657, 32238, 31942, 32050, 20197, 16330, 22356, 24997, 24617, 23812, 21587, 19506, 18871, 27554, 20895, 15593, 12505, 9459, 16454, 13315, 14297, 17989, 12435, 9695, 10445, 14533, 10852, 7649, 7483, 10817, 8626, 10595, 7978, 7011, 9390, 7027, 9567, 7876, 9150, 6743, 7696, 5596, 7206, 7421, 5094, 5849, 5337, 4698, 3328, 4410, 4055, 3146, 2901, 2574, 2314, 1690, 1398, 1879, 1391, 1386, 1412, 1207, 1121, 1128, 1299, 1111, 1249, 1259, 969, 991, 851, 890, 689, 603, 471, 461, 457, 401, 353, 404, 357, 298, 446, 374, 421, 433, 306, 264, 272, 254, 222, 175, 125, 127, 128, 144, 62, 35, 15, 9, 5, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    //     [0, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1, 0, 1, 1, 4, 2, 2, 1, 2, 1, 5, 3, 4, 6, 4, 5, 5, 10, 18, 44, 104, 161, 298, 508, 759, 1176, 1348, 1591, 1909, 2613, 3963, 5134, 6559, 9479, 12759, 14586, 17718, 23907, 30383, 34941, 36883, 37706, 41198, 40213, 36242, 40598, 55863, 60826, 62088, 57088, 52087, 55584, 57170, 52184, 45009, 41956, 38155, 33990, 33314, 34776, 37096, 40357, 45073, 40175, 27279, 24692, 24405, 21576, 18241, 18770, 19999, 22550, 21136, 15245, 13968, 15020, 16661, 15028, 12625, 14482, 14794, 11418, 10849, 11670, 10809, 10626, 10878, 9819, 8709, 7694, 7643, 5300, 6066, 6954, 6644, 4789, 3272, 2238, 2391, 2335, 2164, 2034, 2116, 1920, 1738, 1346, 1084, 1522, 1517, 1460, 1494, 1636, 1687, 1598, 1687, 2029, 1847, 1616, 1726, 1898, 1814, 1769, 1591, 1304, 1266, 1513, 1462, 1042, 932, 1138, 1048, 818, 815, 611, 565, 500, 393, 441, 431, 404, 315, 314, 374, 432, 338, 241, 240, 258, 226, 151, 150, 122, 166, 105, 67, 59, 34, 19, 18, 3, 5, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    // ];
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



function getHistogram(image: Image2D): Histogram {

    const pixels = image.pixels;

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

    for (let y = min_y; y < max_y; y++) {
        for (let x = min_x; x < max_x; x++) {
            const dx = x - center.x;
            const dy = y - center.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist <= radius) {
                const i = 4 * ((y * image.width) + x);
                r[pixels[i]]++;
                g[pixels[i + 1]]++;
                b[pixels[i + 2]]++;
            }
        }
    }

    return { r, g, b }
}

function calculateMeanAndStd(histogram: Int32Array) {
    const numPixels = histogram.reduce((sum, bin) => sum + bin, 0);
    const mean = histogram.reduce((sum, bin, intensity) => sum + intensity * bin, 0) / numPixels;
    const variance = histogram.reduce((sum, bin, intensity) => sum + bin * ((intensity - mean) ** 2), 0) / numPixels;
    const std = Math.sqrt(variance);
    return { mean, std };
}

const fs_standardize = `#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;

uniform vec3 u_mean;
uniform vec3 u_std;

layout(location = 0) out vec4 color_out;

// target values: https://tvst.arvojournals.org/article.aspx?articleid=2610947
// red brightness = 192, green brightness = 96, blue brightness = 32; red span = 128, green span = 128, blue span = 32

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 source = 255.0 * texture(u_source, uv).rgb;
    vec3 alpha = vec3(128, 128, 32) / (4.0 * u_std);
    
    color_out.rgb = (vec3(192, 96, 32) + alpha * (source - u_mean)) / 255.0;
    color_out.a = 1.0;
}`;

const fs_lut = `#version 300 es
precision highp float;
precision highp sampler2D;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;
uniform vec3[256] u_lut;

layout(location = 0) out vec4 color_out;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 source = texture(u_source, uv).rgb;

    color_out.r = u_lut[int(255.0 * source.r)].r;
    color_out.g = u_lut[int(255.0 * source.g)].g;
    color_out.b = u_lut[int(255.0 * source.b)].b;
    color_out.a = 1.0;
}`;