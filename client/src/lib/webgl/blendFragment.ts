/** Sample coordinate that fails the in-bounds test, so the layer adds nothing. */
export const UNMAPPED_LAYER = `vec2 mapping(vec2 uv) { return vec2(-1.0); }`;

/**
 * Mapping read from `u_affine<layer>` (layer pixels from first-image pixels),
 * so editing points changes a uniform instead of the shader source.
 */
export const AFFINE_UNIFORM_LAYER = "affine-uniform";

export const COMPOSITE_OVERLAY = 0;
export const COMPOSITE_CHECKERBOARD = 1;

/**
 * One fragment shader for a stack of registered layers. Each mapping is a
 * baked `vec2 mapping(vec2 uv)` from the first image into that layer, or
 * `AFFINE_UNIFORM_LAYER`. Styles, weights, and the composite mode are uniforms.
 *
 * Overlay sums each layer per channel and divides by how much of that channel
 * the layers cover, so complementary tints add and matching ones average.
 * Checkerboard shows one layer per tile and falls back to the first layer
 * where the tile's layer has no sample.
 */
export function blendFragment(mappings: readonly string[]): string {
    const count = mappings.length;
    const declarations = mappings
        .map((mapping, layer) => layerDeclarations(mapping, layer))
        .join("\n");
    const samples = mappings
        .map(
            (_, layer) => `    {
        vec2 uv = mapping_${layer}(v_uv);
        alphas[${layer}] = u_weight${layer} * blend_inside(uv);
        colours[${layer}] = layer_colour(texture(u_layer${layer}, uv).rgb, u_wl${layer}, u_channel${layer}, u_tint${layer}, u_colour${layer});
        coverage[${layer}] = mix(vec3(1.0), u_colour${layer}, u_tint${layer});
    }`,
        )
        .join("\n");

    return `#version 300 es
precision highp float;

const int LAYERS = ${count};
const vec3 LUMA = vec3(0.299, 0.587, 0.114);

uniform vec2 u_window_level;
uniform vec2 u_size_anchor;
uniform int u_composite;
uniform float u_tile;

${declarations}

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

float blend_inside(vec2 uv) {
    return step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
}

vec3 layer_colour(vec3 rgb, vec2 wl, int channel, float tint, vec3 colour) {
    vec3 c = clamp((255.0 * rgb - wl.x) / max(wl.y - wl.x, 1e-3), 0.0, 1.0);
    if (channel == -1) {
        c = vec3(dot(c, LUMA));
    } else if (channel >= 0) {
        c = vec3(c[channel]);
    }
    return mix(c, dot(c, LUMA) * colour, tint);
}

void main() {
    float alphas[LAYERS];
    vec3 colours[LAYERS];
    vec3 coverage[LAYERS];
${samples}

    vec3 rgb = vec3(0.0);
    if (u_composite == ${COMPOSITE_CHECKERBOARD}) {
        vec2 cell = floor(v_uv * u_size_anchor / max(u_tile, 1.0));
        int layer = int(mod(cell.x + cell.y, float(LAYERS)));
        if (alphas[layer] <= 0.0) layer = 0;
        rgb = alphas[layer] * colours[layer];
    } else {
        vec3 total = vec3(0.0);
        vec3 covered = vec3(0.0);
        for (int i = 0; i < LAYERS; i++) {
            total += alphas[i] * colours[i];
            covered += alphas[i] * coverage[i];
        }
        rgb = total / max(vec3(1.0), covered);
    }

    color_out.rgb = (255.0 * rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}
`;
}

function layerDeclarations(mapping: string, layer: number): string {
    const uniforms = `uniform sampler2D u_layer${layer};
uniform float u_weight${layer};
uniform vec2 u_wl${layer};
uniform int u_channel${layer};
uniform float u_tint${layer};
uniform vec3 u_colour${layer};`;
    if (mapping === AFFINE_UNIFORM_LAYER) {
        return `${uniforms}
uniform mat3 u_affine${layer};
uniform vec2 u_size${layer};
vec2 mapping_${layer}(vec2 uv) {
    vec3 p = u_affine${layer} * vec3(uv * u_size_anchor, 1.0);
    return p.xy / p.z / u_size${layer};
}`;
    }
    return `${uniforms}
${prefixMapping(mapping, layer)}`;
}

/** Give every helper a layer prefix so several baked paths can share one shader. */
function prefixMapping(mapping: string, layer: number): string {
    return mapping
        .replace(/vec2\s+map_(\d+)\s*\(/g, `vec2 map_l${layer}_$1(`)
        .replace(/\bmap_(\d+)\s*\(/g, `map_l${layer}_$1(`)
        .replace(/vec2\s+mapping\s*\(/g, `vec2 mapping_${layer}(`);
}
