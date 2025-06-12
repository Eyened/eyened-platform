#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_bitmask;

uniform sampler2D u_drawing;
uniform bool u_paint;

layout(location = 0) out uint out_value;

void erase() {
    out_value &= ~u_bitmask;
}

void draw() {
    out_value |= u_bitmask;
}

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    out_value = texelFetch(u_current, coord, 0).r;

    bool value = texelFetch(u_drawing, coord, 0).r > 0.f;

    if(value) {
        if(u_paint) {
            draw();
        } else {
            erase();
        }
    }
}
