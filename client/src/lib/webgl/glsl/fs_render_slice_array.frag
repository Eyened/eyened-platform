#version 300 es
precision highp float;
precision highp sampler2DArray;

uniform sampler2DArray u_image;
uniform int u_index;
uniform vec2 u_window_level;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    // sampler2DArray layer index is not normalized (unlike sampler3D depth)
    float i = texture(u_image, vec3(v_uv, float(u_index))).x;
    float g =
        (255.0f * i - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out = vec4(g, g, g, 1.0f);
}
