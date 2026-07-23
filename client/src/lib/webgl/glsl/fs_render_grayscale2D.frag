#version 300 es
precision highp float;

uniform sampler2D u_image;
uniform vec2 u_window_level;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    float i = texture(u_image, v_uv).r;
    float g =
        (255.0f * i - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out = vec4(g, g, g, 1.0f);
}
