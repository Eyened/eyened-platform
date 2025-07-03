#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;
uniform vec3 u_image_size;

uniform usampler2D u_annotation;
uniform float u_alpha;
uniform vec3[32] u_colors;
uniform int u_highlighted_feature_index;

uniform bool u_smooth;
uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

float getAlphaQuestionable(float a, bool layer_annotation) {

	// block pattern
    float bandWidth = 20.0f;
    vec2 blockCoord = mod(gl_FragCoord.xy, bandWidth);
    float brightness = 0.0f;
    int x = int((blockCoord.x < bandWidth / 2.0f));
    int y = int((blockCoord.y < bandWidth / 2.0f));
    if((x ^ y) > 0) {
        brightness = 1.0f;
    }
    if(layer_annotation)
        return 0.5f * a + 0.5f * brightness;
    else
        return 0.5f * brightness;
}


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

    uint annotation = texture(u_annotation, v_uv).r;

    bool has_layer = annotation > 0u;
    
    float layer_alpha;

    color_out = vec4(0.0f);
    if(has_layer) {
        vec3 accumulated_color = vec3(0.0f);
        float count = 0.0f;

        for(uint i = 0u; i < 32u; i++) {
            // loop over bitmasks

            // i = 0 | mask = 0001 | feature_index 1 = 0001
            // i = 1 | mask = 0010 | feature_index 2 = 0010
            // i = 2 | mask = 0100 | feature_index 3 = 0100
            // i = 3 | mask = 1000 | feature_index 4 = 1000
            // etc
            uint mask = 1u << i;
          
            if((annotation & mask) != 0u) {
                int feature_index = int(i) + 1;

                vec3 layer_color = u_colors[feature_index - 1];
                if(u_highlighted_feature_index == 0 || (u_highlighted_feature_index == feature_index)) {
                    layer_alpha = 1.0f;
                } else {
                    layer_alpha = 0.3f;
                }
                // accumulate possibly overlapping colors
                accumulated_color += layer_color * layer_alpha;
                count += layer_alpha;
            }
        }

        // calculate average color
        if(count > 0.0f) {
            accumulated_color /= count;
        }
        color_out = vec4(accumulated_color, u_alpha);
    }

}