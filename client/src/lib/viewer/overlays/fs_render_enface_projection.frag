#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_thickness;
uniform vec3 u_color;
uniform float u_min_thickness;
uniform float u_max_thickness;
uniform float u_alpha;
uniform int u_mode;
uniform vec3 u_image_size;
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

void main() {
    color_out = vec4(0.0);
    float thickness = texture(u_thickness, v_uv).r;
    if(thickness <= 0.0) {
        return;
    }

    if(u_mode == 0) {
        // Mask: any thickness > 0 renders as a flat feature color.
        vec4 feature_color = vec4(u_color, 1.0);
        color_out = mix(vec4(0.0), feature_color, u_alpha);
    } else {
        // Heatmap: stretch foreground thickness between min and max.
        float range = max(u_max_thickness - u_min_thickness, 1e-6);
        float normalized = clamp((thickness - u_min_thickness) / range, 0.0, 1.0);
        color_out.rgb = heatmap(normalized);
        color_out.a = u_alpha * max(normalized, 0.35);
    }
}
