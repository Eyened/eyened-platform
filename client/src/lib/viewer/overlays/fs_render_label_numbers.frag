#version 300 es
precision highp usampler3D;
precision highp float;
precision highp int;

uniform usampler3D u_annotation;
uniform uint u_questionable_bit;

uniform float u_alpha;
uniform vec3[32] u_colors;
uniform int u_highlight;

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
    if(has_layer) {

        vec3 color = u_colors[(annotation - 1u) % 32u];
        color_out = vec4(color, alpha);

        if(u_highlight == 0 || u_highlight == int(annotation))
            color_out.a = u_alpha;
        else
            color_out.a = 0.3f;
    }
    if((annotation & u_questionable_bit) > 0u) {
        color_out.a = getAlphaQuestionable(color_out.a, has_layer);
    }

}