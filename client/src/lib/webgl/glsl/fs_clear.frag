#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_bitmask;

layout(location = 0) out uvec2 color_out;

void main() {
    // r = annotation, g = questionable
    color_out = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).rg;
    color_out.r &= ~u_bitmask;
    color_out.g &= ~u_bitmask;   
    
}