#version 300 es
precision highp float;
precision highp sampler3D;

uniform sampler3D u_image;
uniform sampler3D u_flow;
uniform vec3 u_image_size;
uniform int u_index;
uniform vec2 u_window_level;
// 0 = structural OCT, 1 = angio_flow alone, 2 = structural + red flow overlay
uniform int u_angio_mode;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

float apply_window_level(float i) {
    return (255.0f * i - u_window_level.x) / (u_window_level.y - u_window_level.x);
}

void main() {
    vec3 uvw = vec3(v_uv, (float(u_index) + 0.5f) / u_image_size.z);
    float s = texture(u_image, uvw).x;
    float f = texture(u_flow, uvw).x;

    if (u_angio_mode == 1) {
        float g = apply_window_level(f);
        color_out = vec4(g, g, g, 1.0f);
        return;
    }

    float g = apply_window_level(s);
    if (u_angio_mode == 2) {
        // Low flow → transparent; higher flow → more opaque red over OCT
        vec3 base = vec3(g);
        color_out = vec4(mix(base, vec3(1.0f, 0.0f, 0.0f), f), 1.0f);
        return;
    }

    color_out = vec4(g, g, g, 1.0f);
}
