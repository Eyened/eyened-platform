#version 300 es
precision highp sampler2D;  
precision highp float;

uniform sampler2D u_import;

layout(location = 0) out float out_value;

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    out_value = texelFetch(u_import, coord, 0).r;
}
