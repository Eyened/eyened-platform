#version 300 es
precision highp usampler3D;
precision highp float;
precision highp int;

uniform usampler3D u_annotation;
uniform uint u_questionable_bit;
uniform float u_alpha;
uniform vec3[32] u_colors;
uniform uint u_highlight;

in vec3 v_uv;

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

void main() {
    // v_uv: width, height, depth
    uint annotation = texture(u_annotation, v_uv).r;

    bool has_layer = (annotation & ~u_questionable_bit) > 0u;
    
    float alpha = u_alpha;

    color_out = vec4(0.0f);
    if(has_layer) {
        vec4 accumulated_color = vec4(0.0f);
        uint count = 0u;

        for(uint i = 0u; i < 16u; i++) {
            if((annotation & (1u << i)) != 0u) {
                vec4 layer_color = vec4(u_colors[i], 1.0f);
                // accumulate colors
                accumulated_color += layer_color;
                count++;
            }
        }

        // calculate average color
        if(count > 0u) {
            accumulated_color /= float(count);
        }

        // blend color_out with average color
        if(u_highlight == 0u || (u_highlight & annotation) != 0u) {
            color_out = mix(color_out, accumulated_color, alpha);
        } else {
            color_out = mix(color_out, accumulated_color, 0.3f);
        }
    }

    if((annotation & u_questionable_bit) > 0u) {
        color_out.a = getAlphaQuestionable(color_out.a, has_layer);
    }

}