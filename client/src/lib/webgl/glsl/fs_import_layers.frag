#version 300 es
precision highp usampler2D;
precision highp int;

uniform usampler2D u_import;

layout(location = 0) out uint color_out;

void main() {
    color_out = texelFetch(u_import, ivec2(gl_FragCoord.xy), 0).r;
}