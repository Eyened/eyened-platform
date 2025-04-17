#version 300 es
precision highp float;

uniform sampler2D u_image;
uniform vec2 u_window_level;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    vec3 color_primary = texture(u_image, v_uv).rgb;    
    
    color_out.rgb = color_primary;
    color_out.rgb = (255.0 * color_out.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}