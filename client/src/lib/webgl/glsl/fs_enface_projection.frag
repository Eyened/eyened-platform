#version 300 es
precision highp float;
precision highp sampler3D;

uniform sampler3D u_volumeTexture;
uniform int u_height;  

out uint sum;

void main() {
    sum = 0u;
    for (int z = 0; z < u_height; z++) {
        ivec3 loc = ivec3(int(gl_FragCoord.x), z, int(gl_FragCoord.y));
        sum += uint(texelFetch(u_volumeTexture, loc, 0).r * 255.0);
    }
}