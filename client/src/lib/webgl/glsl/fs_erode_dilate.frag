#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_bitmask;

uniform sampler2D u_drawing;
uniform bool u_paint;

layout(location = 0) out uint out_value;

ivec2 offsets[4] = ivec2[4](ivec2(1, 0),// Right neighbor
ivec2(0, 1),// Bottom neighbor
ivec2(-1, 0),// Left neighbor
ivec2(0, -1)// Top neighbor
);

bool withinBounds(ivec2 pos) {
    ivec2 size = textureSize(u_current, 0).xy;
    return pos.x >= 0 && pos.x < size.x && pos.y >= 0 && pos.y < size.y;
}

uint getPixel(ivec2 pos) {
    return texelFetch(u_current, pos, 0).r;
}

void erase() {
    out_value &= ~u_bitmask;
}

void draw() {
    out_value |= u_bitmask;
}

void erode(ivec2 pos) {
    for(int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + offsets[i];
        if(withinBounds(neighborPos)) {
            uint neighbor = getPixel(neighborPos);
            if((neighbor & u_bitmask) == 0u) {
                erase();
                return;
            }
        }
    }
}

void dilate(ivec2 pos) {
    for(int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + offsets[i];
        if(withinBounds(neighborPos)) {
            uint neighbor = getPixel(neighborPos);
            if((neighbor & u_bitmask) > 0u) {
                draw();
                return;
            }
        }
    }
}

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    out_value = texelFetch(u_current, coord, 0).r;
    bool value = texelFetch(u_drawing, coord, 0).r > 0.f;

    if(value) {
        if(u_paint) {
            dilate(coord);
        } else {
            erode(coord);
        }
    }
}