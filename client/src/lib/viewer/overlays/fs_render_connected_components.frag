#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform usampler2D u_annotation;

uniform float u_alpha;
uniform vec3[256] u_colors;

uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;
uniform vec3 u_image_size;
uniform bool u_smooth;

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

float bilinear(usampler2D binary_mask, uint bitmask, vec2 pos) {
    ivec2 ipos = ivec2(pos);
    bool t00 = (bitmask & texelFetch(binary_mask, ipos, 0).r) > 0u;
    bool t10 = (bitmask & texelFetch(binary_mask, ipos + ivec2(1, 0), 0).r) > 0u;
    bool t01 = (bitmask & texelFetch(binary_mask, ipos + ivec2(0, 1), 0).r) > 0u;
    bool t11 = (bitmask & texelFetch(binary_mask, ipos + ivec2(1, 1), 0).r) > 0u;

    vec2 f = fract(pos);
    float u0 = mix(float(t00), float(t10), f.x);
    float u1 = mix(float(t01), float(t11), f.x);
    float u = mix(u0, u1, f.y);
    return u;
}

bool getMask(usampler2D mask, uint bitmask, vec2 pos) {
    if(u_smooth) {
        return bilinear(mask, bitmask, pos) > 0.5f;
    } else {
        return (bitmask & texelFetch(mask, ivec2(pos), 0).r) > 0u;
    }
}

void main() {
    vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
    if(u_has_mask) {
        if (!getMask(u_mask, u_mask_bitmask, p)) {
            discard;
        }
    }
    uint i = texture(u_annotation, v_uv).r;
    if(i == 0u) {
        discard;
    }
    vec3 color = u_colors[(i - 1u) % 256u];
    color_out = vec4(color, u_alpha);    

}