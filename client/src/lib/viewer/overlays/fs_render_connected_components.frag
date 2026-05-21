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
in vec2 v_uv;
layout(location = 0) out vec4 color_out;

bool getMask(usampler2D mask, uint bitmask, vec2 pos) {
    return (bitmask & texelFetch(mask, ivec2(pos), 0).r) > 0u;
}

void main() {
    vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
    if(u_has_mask) {
        if (!getMask(u_mask, u_mask_bitmask, p)) {
            discard;
        }
    }
    uint i = texelFetch(u_annotation, ivec2(p), 0).r;
    if(i == 0u) {
        discard;
    }
    vec3 color = u_colors[(i - 1u) % 256u];
    color_out = vec4(color, u_alpha);    

}