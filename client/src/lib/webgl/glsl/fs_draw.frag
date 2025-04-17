#version 300 es
precision highp usampler2D;
precision highp float;

uniform sampler2D u_drawing;
uniform usampler2D u_current;
uniform uint u_bitmask;
uniform bool u_questionable;
uniform bool u_paint;

layout(location = 0) out uvec2 color_out;
void main() {

    bool drawing = texelFetch(u_drawing, ivec2(gl_FragCoord.xy), 0).r > 0.0f;

    // r = label, g = questionable
    color_out = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).rg;

    if(drawing) {
        if(u_paint) {
            if(u_questionable)
                color_out.g |= u_bitmask;
            else
                color_out.r |= u_bitmask;
        } else {
            if(u_questionable)
                color_out.g &= ~u_bitmask;
            else
                color_out.r &= ~u_bitmask;
        }
    }
}
