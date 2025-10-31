#version 300 es
precision highp float;

uniform sampler2D u_input;   // source texture (R32F for first pass, RG32F for subsequent)
uniform ivec2 u_srcSize;     // source texture size
uniform bool u_firstPass;    // true if input is R32F (single channel), false if RG32F (min/max pair)

out vec2 minmax;             // RG32F target: R=min, G=max

vec2 readMinMax(ivec2 p) {
    if (u_firstPass) {
        float v = texelFetch(u_input, p, 0).r;
        return vec2(v, v);  // both min and max are the same value
    } else {
        return texelFetch(u_input, p, 0).rg;
    }
}

void main() {
    // Each output pixel corresponds to a 2x2 block in the input
    ivec2 dst = ivec2(gl_FragCoord.xy);
    ivec2 base = dst * 2;

    // Gather up to 4 samples, clamping at edges
    vec2 a = readMinMax(clamp(base + ivec2(0, 0), ivec2(0), u_srcSize - 1));
    vec2 b = readMinMax(clamp(base + ivec2(1, 0), ivec2(0), u_srcSize - 1));
    vec2 c = readMinMax(clamp(base + ivec2(0, 1), ivec2(0), u_srcSize - 1));
    vec2 d = readMinMax(clamp(base + ivec2(1, 1), ivec2(0), u_srcSize - 1));

    // Compute min of all min values, max of all max values
    float minVal = min(min(a.x, b.x), min(c.x, d.x));
    float maxVal = max(max(a.y, b.y), max(c.y, d.y));
    
    minmax = vec2(minVal, maxVal);
}


