#version 300 es
precision highp sampler2D;
precision highp usampler2D;
precision highp float;
precision highp int;
uniform vec3 u_image_size;

uniform sampler2D u_annotation;
uniform float u_threshold;
uniform bool u_hard;

uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;

uniform vec3 u_color;
uniform bool u_show_seg_bounds;
in vec2 v_uv;


bool getMask(usampler2D mask, uint bitmask, vec2 pos) {
    return (bitmask & texelFetch(mask, ivec2(pos), 0).r) > 0u;
}

layout(location = 0) out vec4 color_out;

void main() {
    vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
    if(u_has_mask) {
        if (!getMask(u_mask, u_mask_bitmask, p)) {
            discard;
        }
    }

    if (isSegPlaneOutlineScreen()) {
        color_out = segPlaneOutlineColor();
        return;
    }

    color_out = vec4(0.0);
    float val = texture(u_annotation, v_uv).r;

    if (u_hard) {
        if (val > u_threshold) {
            color_out = vec4(u_color, 1);
        }
    } else {
        if (val < u_threshold) {
            color_out = vec4(1, 1, 1, val);
        } else if (val > u_threshold) {
            color_out = vec4(u_color, 1);
        }
    }

    applySegPlaneOutline(color_out);

}