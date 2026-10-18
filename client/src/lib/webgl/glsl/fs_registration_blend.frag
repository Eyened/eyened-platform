#version 300 es
precision highp float;

uniform sampler2D u_fixed;
uniform sampler2D u_overlay;
uniform mat3 u_affine;
uniform vec2 u_size_fixed;
uniform vec2 u_size_overlay;
uniform float u_has_overlay;
uniform float u_fixed_mix;
uniform float u_overlay_mix;
uniform float u_fixed_opacity;
uniform float u_overlay_opacity;
uniform vec3 u_fixed_colour;
uniform vec3 u_overlay_colour;
uniform vec2 u_window_level;

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

vec2 map_overlay(vec2 uv) {
    vec3 transformed = u_affine * vec3(uv * u_size_fixed, 1.0);
    vec2 result = transformed.xy / transformed.z;
    return result / u_size_overlay;
}

vec3 tinted(vec3 rgb, float amount, vec3 colour) {
    float luma = dot(rgb, vec3(0.299, 0.587, 0.114));
    return mix(rgb, luma * colour, amount);
}

void main() {
    vec3 rgb = u_fixed_opacity * tinted(texture(u_fixed, v_uv).rgb, u_fixed_mix, u_fixed_colour);

    vec2 overlay_uv = map_overlay(v_uv);
    float inside = step(0.0, overlay_uv.x) * step(overlay_uv.x, 1.0)
        * step(0.0, overlay_uv.y) * step(overlay_uv.y, 1.0);
    vec3 overlay_rgb = texture(u_overlay, overlay_uv).rgb;
    rgb += u_has_overlay * u_overlay_opacity * inside * tinted(overlay_rgb, u_overlay_mix, u_overlay_colour);

    color_out.rgb = (255.0 * rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}
