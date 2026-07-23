#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_mask;
uniform int height;
uniform float u_inv_height;

out float sum;

void main() {
    sum = 0.0;
    ivec2 loc = ivec2(gl_FragCoord.xy);
    for(int y = 0; y < height; y++) {
        ivec2 maskLoc = ivec2(loc.x, y);
        sum += texelFetch(u_mask, maskLoc, 0).r;
    }
    sum *= u_inv_height;
}
