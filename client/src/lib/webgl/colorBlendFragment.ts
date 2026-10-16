export function colorBlendFragment(mappings: readonly string[]): string {
    const renamed = mappings.map((mapping, index) =>
        mapping.replace(/vec2\s+mapping\s*\(/g, `vec2 mapping_${index}(`),
    );
    const samplers = [
        "uniform sampler2D u_layer0;",
        "uniform vec3 u_colour0;",
        "uniform float u_untinted0;",
        ...mappings.flatMap((_, index) => {
            const n = index + 1;
            return [
                `uniform sampler2D u_layer${n};`,
                `uniform vec3 u_colour${n};`,
                `uniform float u_untinted${n};`,
            ];
        }),
    ];
    const samples = [
        "vec3 rgb = vec3(0.0);",
        "vec3 sample0 = texture(u_layer0, v_uv).rgb;",
        "float luma0 = dot(sample0, vec3(0.299, 0.587, 0.114));",
        "rgb += mix(luma0 * u_colour0, sample0, u_untinted0);",
        ...mappings.map((_, index) => {
            const n = index + 1;
            return [
                `vec3 sample${n} = texture(u_layer${n}, mapping_${index}(v_uv)).rgb;`,
                `float luma${n} = dot(sample${n}, vec3(0.299, 0.587, 0.114));`,
                `rgb += mix(luma${n} * u_colour${n}, sample${n}, u_untinted${n});`,
            ].join("\n    ");
        }),
    ];
    return `#version 300 es
precision highp float;
uniform vec2 u_window_level;
in vec2 v_uv;
layout(location = 0) out vec4 color_out;
${samplers.join("\n")}
${renamed.join("\n")}
void main() {
    ${samples.join("\n    ")}
    color_out.rgb = (255.0 * rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}
`;
}
