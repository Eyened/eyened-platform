#version 300 es
precision highp float;
precision highp sampler3D;

uniform sampler3D u_image;
uniform vec3 u_image_size;
uniform int u_index;
uniform vec2 u_window_level;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    vec3 uvw = vec3(v_uv, (float(u_index) + 0.5f) / u_image_size.z);
    float i = texture(u_image, uvw).x;
    float g = (255.0f * i - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out = vec4(g, g, g, 1);
}