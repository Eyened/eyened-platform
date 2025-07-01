#version 300 es
precision highp sampler2D;
precision highp float;
precision highp int;

uniform sampler2D u_annotation;
uniform float u_threshold;
uniform bool u_hard;

uniform vec3 u_color;
in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    float val = texture(u_annotation, v_uv).r;
    
    if (u_hard) {
        if (val > u_threshold) {
            color_out = vec4(u_color, 1);
        } 
    } else {
        if (val < u_threshold) {
            color_out = vec4(1, 1, 1, val);
        } else if (val > u_threshold) {
            color_out = vec4(u_color, 1);
        }
    }
}