#version 300 es
precision highp usampler2D;
precision highp float;

uniform sampler2D u_drawing;
uniform usampler2D u_current;
uniform uint u_bitmask;
uniform bool u_questionable;
uniform bool u_paint;

layout(location = 0) out uvec2 color_out;

ivec2 offsets[4] = ivec2[4](ivec2(1, 0),   // Right neighbor
ivec2(0, 1),   // Bottom neighbor
ivec2(-1, 0),  // Left neighbor
ivec2(0, -1)   // Top neighbor
);

bool withinBounds(ivec2 pos) {
    ivec2 size = textureSize(u_current, 0).xy;
    return pos.x >= 0 && pos.x < size.x && pos.y >= 0 && pos.y < size.y;
}
uint getPixel(ivec2 pos) {
    if(u_questionable)
        return texelFetch(u_current, pos, 0).g;
    else
        return texelFetch(u_current, pos, 0).r;
}

void erase() {
    if(u_questionable)
        color_out.g &= ~u_bitmask;
    else
        color_out.r &= ~u_bitmask;
}

void draw() {
    if(u_questionable)
        color_out.g |= u_bitmask;
    else
        color_out.r |= u_bitmask;
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
    ivec2 pos = ivec2(gl_FragCoord.xy);

    color_out = texelFetch(u_current, pos, 0).rg;

    bool hasDrawing;
    if(u_questionable)
        hasDrawing = (color_out.g & u_bitmask) > 0u;
    else
        hasDrawing = (color_out.r & u_bitmask) > 0u;

    bool drawing = texelFetch(u_drawing, ivec2(gl_FragCoord.xy), 0).r > 0.0f;

    if(drawing) {
        if(u_paint) {
            if(!hasDrawing) {
                dilate(pos);
            }
        } else {
            if(hasDrawing) {
                erode(pos);
            }
        }
    }

}