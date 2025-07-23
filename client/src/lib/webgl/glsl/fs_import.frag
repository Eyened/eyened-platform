#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_bitmask;

uniform sampler2D u_import;
uniform float u_threshold;
uniform int u_import_channel;
layout(location = 0) out uint out_value;

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    out_value = texelFetch(u_current, coord, 0).r;
    vec4 value_vec = texelFetch(u_import, coord, 0);
    float value;
    if(u_import_channel == 0) {
        value = value_vec.r;
    } else if(u_import_channel == 1) {
        value = value_vec.g;
    } else if(u_import_channel == 2) {
        value = value_vec.b;
    } else if(u_import_channel == 3) {
        value = value_vec.a;
    }
    if(value > u_threshold) {
        out_value |= u_bitmask;
    } else {
        out_value &= ~u_bitmask;
    }
}