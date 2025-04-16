#version 300 es
precision highp usampler2D;
precision highp int;

uniform usampler2D u_drawing;
uniform usampler2D u_current;
uniform uint u_questionable_bit;
uniform uint u_featureValue;

layout(location = 0) out uint color_out;
void main() {

    uvec2 pix = texelFetch(u_drawing, ivec2(gl_FragCoord.xy), 0).xy;
    color_out = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).r;

    uint current_questionable = color_out & u_questionable_bit;

    //drawing
    if(pix.x > 0u) {
        if(u_featureValue == u_questionable_bit) {
            color_out |= u_questionable_bit;
        } else {
            color_out = u_featureValue | current_questionable;
        }
    }

    // erasing
    if(pix.y > 0u) {
        if(u_featureValue == u_questionable_bit) {
            color_out &= ~u_questionable_bit;
        } else {
            color_out = current_questionable;
        }
    }
}