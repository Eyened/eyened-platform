#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_bitmask;

uniform sampler2D u_drawing;
uniform bool u_paint; // true: paint, false: erase
uniform bool u_mode; // true: multi-label, false: multi-class

layout(location = 0) out uint out_value;

void toggle_multi_label() {
    if(u_paint) {
        // add bits in u_bitmask to out_value
        out_value |= u_bitmask;
    } else {
        // remove bits in u_bitmask from out_value
        out_value &= ~u_bitmask;
    }
}
void toggle_multi_class() {
    if (u_paint) {
        // set out_value to u_bitmask
        out_value = u_bitmask;
    } else {
        // remove only if current class is set
        if (out_value == u_bitmask) {
            out_value = 0u;
        } 
    }
}
void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);

    out_value = texelFetch(u_current, coord, 0).r;
    bool drawing = texelFetch(u_drawing, coord, 0).r > 0.f;

    if(drawing) {
        if(u_mode) {
            toggle_multi_label();
        } else {
            toggle_multi_class();
        }
    }
}
