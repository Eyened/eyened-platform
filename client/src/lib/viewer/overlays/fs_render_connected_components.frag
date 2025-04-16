#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform usampler2D u_annotation;

uniform float u_alpha;
uniform vec3[256] u_colors;

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

void main() {

    uint i = texture(u_annotation, v_uv).r;
    if(i == 0u) {
        discard;
    }
    vec3 color = u_colors[i - 1u];
    color_out = vec4(color, u_alpha);    

}