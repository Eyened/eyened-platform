#version 300 es
precision highp float;
precision highp usampler2D;

uniform usampler2D u_mask;
uniform uint u_feature_bitmask;
uniform int height;
uniform float u_inv_height;

out float sum;

void main() {
    sum = 0.0;
    ivec2 loc = ivec2(gl_FragCoord.xy);
    for(int y = 0; y < height; y++) {
        ivec2 maskLoc = ivec2(loc.x, y);
        uint val = texelFetch(u_mask, maskLoc, 0).r;
        if((val & u_feature_bitmask) > 0u) {
            sum += 1.0;
        }
    }
    sum *= u_inv_height;
}
