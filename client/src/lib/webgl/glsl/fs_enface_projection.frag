#version 300 es
precision highp float;
precision highp sampler3D;
precision highp usampler2D;

uniform sampler3D u_volume;
uniform usampler2D u_top;
uniform usampler2D u_bottom;

out uint sum;

void main() {
    sum = 0u;
    ivec2 loc = ivec2(gl_FragCoord.xy);
    int top = int(texelFetch(u_top, loc, 0).r);
    int bottom = int(texelFetch(u_bottom, loc, 0).r);
    for(int z = top; z < bottom; z++) {
        ivec3 loc3 = ivec3(gl_FragCoord.x, z, gl_FragCoord.y);
        float val = texelFetch(u_volume, loc3, 0).r;
        sum += uint(val * 255.0f);
    }
}