#version 300 es
precision highp usampler2D;
precision highp float;

uniform sampler2D u_drawing;
uniform usampler2D u_current;

uniform uint u_bitmask;
uniform bool u_has_questionable_mask;

layout(location = 0) out uvec2 color_out;

uint setColor(float pixColor, uint colorOut, uint bitmask) {
    return (pixColor > 0.5) ? (colorOut | bitmask) : (colorOut & ~bitmask);
}

void main() {
    
    // the color we want to set
    // r > 0.5 -> set bit, r < 0.5 -> unset bit
    vec4 pix = texelFetch(u_drawing, ivec2(gl_FragCoord.xy), 0);

    // copy current color (to leave other bits unaffected)
    color_out = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).rg;

    // always update the red bit
    color_out.r = setColor(pix.r, color_out.r, u_bitmask);
    if (u_has_questionable_mask) {
        // update the green bit (if present in the mask)
        color_out.g = setColor(pix.g, color_out.g, u_bitmask);
    }
    
}