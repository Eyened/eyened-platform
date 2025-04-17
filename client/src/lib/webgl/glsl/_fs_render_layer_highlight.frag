#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform usampler2D u_annotation;
uniform sampler2D u_colorLookup;
uniform float u_alpha;
uniform uint u_questionable_bit;
uniform vec2 u_scale;
uniform int u_highlight_layer_number;
uniform vec2 u_pointer;
uniform vec2 u_image_size;
uniform float u_view_radius;

in vec2 v_uv;

layout(location = 0) out vec4 color_out;

float getAlphaQuestionable(float a, bool layer_annotation) {
    float bandWidth = 2.0f * u_scale.x;

    vec2 fragCoord = gl_FragCoord.xy;
    float p = fragCoord.x - fragCoord.y;
    float brightness = 0.5f + 0.5f * sin(p / bandWidth);
    if(layer_annotation)
        return 0.5f * a + 0.5f * brightness;
    else
        return 0.5f * brightness;
}

void main() {

    uint annotation = texture(u_annotation, v_uv).r;
    int layer = int(annotation & ~u_questionable_bit);

    bool is_questionable = (annotation & u_questionable_bit) > 0u;
    bool has_layer = annotation > 0u;

    float pointer_dist = length(vec2(u_scale.x / u_scale.y, 1.0f) * (u_pointer - u_image_size * v_uv));

    if(u_highlight_layer_number == layer) {
        vec4 layer_color = texelFetch(u_colorLookup, ivec2(0, layer), 0);

        float alpha = u_alpha;
        if(u_view_radius != 0.0f)
            alpha -= smoothstep(u_view_radius, u_view_radius + 1.0f, pointer_dist);

        if(is_questionable)
            alpha = getAlphaQuestionable(alpha, has_layer);
    
        color_out = vec4(layer_color.rgb, alpha);
    } else {
        discard;
    }

}