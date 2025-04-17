#version 300 es
precision highp usampler3D;
precision highp float;
precision highp int;
uniform usampler3D u_boundaries;
uniform int u_layer;
in vec3 v_uv;

uniform float u_scaling;
uniform vec3 u_image_size;


layout(location = 0) out vec4 color_out;

vec3 heatmap(float value) {
    const vec3 c1 = vec3(0, 0, 1);  // Blue
    const vec3 c2 = vec3(0, 1, 0);  // Green
    const vec3 c3 = vec3(1, 1, 0);  // Yellow
    const vec3 c4 = vec3(1, 0, 0);  // Red

    vec3 color;
    if(value < 0.25f) {
        color = mix(c1, c2, value / 0.25f);
    } else if(value < 0.5f) {
        color = mix(c2, c3, (value - 0.25f) / 0.25f);
    } else if(value < 0.75f) {
        color = mix(c3, c4, (value - 0.5f) / 0.25f);
    } else {
        color = c4;
    }

    return color;
}

void main() {

    color_out = vec4(0.0f, 0.0f, 0.0f, 0.0f);

    ivec3 pos = ivec3(v_uv.xy * u_image_size.xy, u_layer);
    uvec2 ILM_boundary = texelFetch(u_boundaries, pos, 0).rg;

    uint thickness = ILM_boundary.g - ILM_boundary.r;

    if(ILM_boundary.g != 0u) {

        float normalizedThickness = float(thickness) / u_scaling;
        color_out.rgb = heatmap(normalizedThickness);
        color_out.a = normalizedThickness;
    }
}