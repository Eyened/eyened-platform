/** Sample coordinate that fails the in-bounds test, so the layer adds nothing. */
export const UNMAPPED_LAYER = `vec2 mapping(vec2 uv) { return vec2(-1.0); }`;

/**
 * One fragment shader for a whole series. Each mapping is a baked
 * `vec2 mapping(vec2 uv)` from the first image into that layer.
 * Each layer has a sampler and a weight uniform.
 */
export function seriesBlendFragment(mappings: readonly string[]): string {
    const layers = mappings.map((mapping, layer) =>
        prefixMapping(mapping, layer),
    );
    const samplers = mappings
        .map((_, layer) => `uniform sampler2D u_layer${layer};`)
        .join("\n");
    const weights = mappings
        .map((_, layer) => `uniform float u_weight${layer};`)
        .join("\n");
    const samples = mappings
        .map(
            (_, layer) => `    vec2 uv${layer} = mapping_${layer}(v_uv);
    rgb += u_weight${layer} * series_inside(uv${layer}) * texture(u_layer${layer}, uv${layer}).rgb;`,
        )
        .join("\n");

    return `#version 300 es
precision highp float;

${samplers}
${weights}
uniform vec2 u_window_level;

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

${layers.join("\n")}

float series_inside(vec2 uv) {
    return step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
}

void main() {
    vec3 rgb = vec3(0.0);
${samples}
    color_out.rgb = (255.0 * rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}
`;
}

/** Give every helper a layer prefix so several baked paths can share one shader. */
function prefixMapping(mapping: string, layer: number): string {
    return mapping
        .replace(/vec2\s+map_(\d+)\s*\(/g, `vec2 map_l${layer}_$1(`)
        .replace(/\bmap_(\d+)\s*\(/g, `map_l${layer}_$1(`)
        .replace(/vec2\s+mapping\s*\(/g, `vec2 mapping_${layer}(`);
}
