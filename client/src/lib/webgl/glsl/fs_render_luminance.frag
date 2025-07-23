#version 300 es
precision highp float;

uniform sampler2D u_image;
uniform vec2 u_window_level;
uniform int u_channel;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    vec3 color_primary = texture(u_image, v_uv).rgb;

    vec3 color = (255.0f * color_primary.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    if (u_channel == -1) {
        float luminance = 0.299f * color.r + 0.587f * color.g + 0.114f * color.b;
        color_out.rgb = vec3(luminance);
    } else if (u_channel == 0) {
        color_out.rgb = vec3(color.r);
    } else if (u_channel == 1) {
        color_out.rgb = vec3(color.g);
    } else if (u_channel == 2) {
        color_out.rgb = vec3(color.b);
    }

    color_out.a = 1.0f;
}