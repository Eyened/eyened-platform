#version 300 es
precision highp sampler2D;
precision highp usampler2D;
precision highp float;
precision highp int;
uniform vec3 u_image_size;

uniform sampler2D u_annotation;
uniform float u_threshold;
uniform bool u_hard;
uniform bool u_smooth;

uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;

uniform vec3 u_color;
in vec2 v_uv;


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


layout(location = 0) out vec4 color_out;

void main() {
    if(u_has_mask) {
        vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
        bool mask = getMask(u_mask, u_mask_bitmask, p);
        if (!mask) {
            discard;
        }
    }
  
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

  

}