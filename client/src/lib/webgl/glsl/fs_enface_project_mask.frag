#version 300 es
precision highp float;
precision highp sampler3D;
precision highp usampler2D;

uniform sampler3D u_volume;
uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform int height;

out float sum;

void main() {
    sum = 0.0;
    ivec2 loc = ivec2(gl_FragCoord.xy);
    // For this x position, loop through all y positions (height) and accumulate mask values
    for(int y = 0; y < height; y++) {
        ivec2 maskLoc = ivec2(loc.x, y);
        uint val = texelFetch(u_mask, maskLoc, 0).r;
        if((val & u_mask_bitmask) > 0u) {
            sum += 1.0;
        }
    }
}