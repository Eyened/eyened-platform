#version 300 es
precision highp sampler2D;
precision highp float;
precision highp int;

uniform sampler2D u_annotation;
uniform float u_threshold;
uniform bool u_hard;
uniform bool u_render_mode;

uniform vec3 u_color;
in vec2 v_uv;

layout(location = 0) out vec4 color_out;

void main() {
    float val = texture(u_annotation, v_uv).r;
    // color_out = vec4(val);
    
    if(val > u_threshold) {
        color_out = vec4(u_color, 1);
    }
}