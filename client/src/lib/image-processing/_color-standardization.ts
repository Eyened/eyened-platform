import { PixelShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { Image2D } from "$lib/webgl/image2D";
import { RenderTexture } from "$lib/webgl/renderTexture";
import { TextureData } from "$lib/webgl/texture";





export function colorStandardization(image: Image2D): { muSigma: TextureData, hist: TextureData } {


    const muSigma = calculateMuSigma(image, histogram);
    const hist = calculateHist(image, histogram);

    return { muSigma, hist };
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





