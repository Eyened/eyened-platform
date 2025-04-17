import { PixelShaderProgram, TextureShaderProgram, TextureShaderProgram3D } from "./FragmentShaderProgram";

import fs_render_features from '$lib/viewer/overlays/fs_render_features.frag';
import fs_render_probability from '$lib/viewer/overlays/fs_render_probability.frag';
import fs_render_connected_components from '$lib/viewer/overlays/fs_render_connected_components.frag';
import fs_render_label_numbers from '$lib/viewer/overlays/fs_render_label_numbers.frag';
import fs_render_layer_bits from '$lib/viewer/overlays/fs_render_layer_bits.frag';
import fs_render_layers_enface from '$lib/viewer/overlays/fs_render_layers_enface.frag';

import fs_draw_enhance from "$lib/webgl/glsl/fs_draw_enhance.frag";
import fs_draw_probability_hard from "$lib/webgl/glsl/fs_draw_probability_hard.frag";
import fs_import from './glsl/fs_import.frag';
import fs_draw from './glsl/fs_draw.frag';
import fs_erode_dilate from './glsl/fs_erode_dilate.frag';
import fs_export from './glsl/fs_export.frag';
import fs_clear from './glsl/fs_clear.frag';

import fs_calculate_boundaries from './glsl/fs_calculate_boundaries.frag';
import fs_enfaceProjection from './glsl/fs_enface_projection.frag';
import type { WebGL } from "./webgl";

/**
 * Centralised place for all shaders used in the viewer
 * This way they don't have to be recompiled every time they are used
 */
export class Shaders {

    renderFeatures: TextureShaderProgram;
    renderProbability: TextureShaderProgram;
    renderConnectedComponents: TextureShaderProgram;
    renderLabelNumbers: TextureShaderProgram3D;
    renderLayerBits: TextureShaderProgram3D;
    renderLayersEnface: TextureShaderProgram;
    drawEnhance: PixelShaderProgram;
    drawHard: PixelShaderProgram;

    import: PixelShaderProgram;
    draw: PixelShaderProgram;
    erodeDilate: PixelShaderProgram;
    export: PixelShaderProgram;
    clear: PixelShaderProgram;

    calculateBoundaries: PixelShaderProgram;
    enfaceProjection: PixelShaderProgram;
    

    constructor(webgl: WebGL) {
        this.renderFeatures = new TextureShaderProgram(webgl, fs_render_features);
        this.renderProbability = new TextureShaderProgram(webgl, fs_render_probability);
        this.renderConnectedComponents = new TextureShaderProgram(webgl, fs_render_connected_components);
        this.renderLabelNumbers = new TextureShaderProgram3D(webgl, fs_render_label_numbers);
        this.renderLayerBits = new TextureShaderProgram3D(webgl, fs_render_layer_bits);
        this.renderLayersEnface = new TextureShaderProgram3D(webgl, fs_render_layers_enface);

        this.drawEnhance = new PixelShaderProgram(webgl, fs_draw_enhance);
        this.drawHard = new PixelShaderProgram(webgl, fs_draw_probability_hard);

        this.calculateBoundaries = new PixelShaderProgram(webgl, fs_calculate_boundaries);
        this.enfaceProjection = new PixelShaderProgram(webgl, fs_enfaceProjection)

        this.import = new PixelShaderProgram(webgl, fs_import);
        this.draw = new PixelShaderProgram(webgl, fs_draw);
        this.erodeDilate = new PixelShaderProgram(webgl, fs_erode_dilate);
        this.export = new PixelShaderProgram(webgl, fs_export);
        this.clear = new PixelShaderProgram(webgl, fs_clear);
    }
}