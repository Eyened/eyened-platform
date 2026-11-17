#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_thickness;
uniform vec3 u_color;
uniform float u_min_thickness;
uniform float u_max_thickness;
uniform float u_alpha;
uniform int u_mode;
uniform int u_nearest_sample;
uniform vec3 u_image_size;
uniform vec2 u_size_primary;
uniform vec2 u_size_secondary;
// Class map pass (u_mode 2): the B-scan's palette and MultiClass opacities.
uniform vec3[32] u_colors;
uniform int u_active_class;
uniform float u_multi_active_alpha;
uniform float u_multi_inactive_alpha;
in vec2 v_uv;

layout(location = 0) out vec4 color_out;

vec3 heatmap(float value) {
    const vec3 c1 = vec3(0.0, 0.0, 1.0);
    const vec3 c2 = vec3(0.0, 1.0, 0.0);
    const vec3 c3 = vec3(1.0, 1.0, 0.0);
    const vec3 c4 = vec3(1.0, 0.0, 0.0);

    if(value < 0.25) {
        return mix(c1, c2, value / 0.25);
    } else if(value < 0.5) {
        return mix(c2, c3, (value - 0.25) / 0.25);
    } else if(value < 0.75) {
        return mix(c3, c4, (value - 0.5) / 0.25);
    }
    return c4;
}

/// @insert mapping

vec4 sampleTexel(vec2 mapped) {
    // Identity `_proj` and class maps: discrete pixels must not bleed via LINEAR.
    if(u_nearest_sample != 0) {
        vec2 sz = u_size_secondary;
        ivec2 tc = ivec2(clamp(floor(mapped * sz), vec2(0.0), sz - 1.0));
        return texelFetch(u_thickness, tc, 0);
    }
    return texture(u_thickness, mapped);
}

void main() {
    color_out = vec4(0.0);
    vec2 mapped = mapping(v_uv);
    if(mapped.x < 0.0 || mapped.x > 1.0 || mapped.y < 0.0 || mapped.y > 1.0) {
        return;
    }

    vec4 texel = sampleTexel(mapped);
    // A class map holds each pixel's class number; colour and opacity as fs_render_multi_class.
    if(u_mode == 2) {
        int cls = int(round(texel.r * 255.0));
        if(cls == 0) {
            return;
        }
        float a = cls == u_active_class ? u_multi_active_alpha : u_multi_inactive_alpha;
        color_out = vec4(u_colors[(cls - 1) & 31], a * u_alpha);
        return;
    }

    float thickness = texel.r;
    if(thickness <= 0.0) {
        return;
    }

    if(u_mode == 0) {
        // Straight alpha, as the B-scan shaders; the blend applies it once.
        color_out = vec4(u_color, u_alpha);
    } else {
        float range = max(u_max_thickness - u_min_thickness, 1e-6);
        float normalized = clamp((thickness - u_min_thickness) / range, 0.0, 1.0);
        color_out.rgb = heatmap(normalized);
        color_out.a = u_alpha * max(normalized, 0.35);
    }
}
