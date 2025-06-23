#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform vec3 u_image_size;

uniform usampler2D u_binary_mask;
uniform uint u_bitmask;

uniform usampler2D u_questionable_mask;
uniform uint u_questionable_bitmask;
uniform bool u_has_questionable_mask;

uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;

uniform bool u_smooth;
uniform bool u_outline;
uniform float u_alpha;
uniform vec3 u_color;

in vec2 v_uv;
layout(location = 0) out vec4 color_out;

// void drawPixelBorder() {
// 	// TODO: calculate strength in vertex shader
// 	float strength = smoothstep(0.0f, 1.0f, 0.01f * ((u_scale * u_image_size).x) / u_viewer_size.x);
// 	vec2 pixel_border = fract(v_uv * u_image_size);
// 	vec2 d = pixel_border - 0.5f;
// 	vec2 d2 = d * d;
// 	float d3 = max(d2.x, d2.y);
// 	float w = 0.5f * strength * smoothstep(0.2f, 0.25f, d3);
// 	color_out = mix(color_out, vec4(1), w);
// }

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

    color_out = vec4(0.0f);

    bool drawing;
    bool questionable;
    bool mask;
    vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
    drawing = getMask(u_binary_mask, u_bitmask, p);
    if(u_has_questionable_mask) {
        questionable = getMask(u_questionable_mask, u_questionable_bitmask, p);
    } else {
        questionable = false;
    }

    if(u_has_mask) {
        mask = getMask(u_mask, u_mask_bitmask, p);
        drawing = drawing && mask;
    }

    if(!(drawing || questionable)) {
        discard;
    }

    vec4 feature_color = vec4(u_color, 1.0f);

    float a = u_alpha;

    if(questionable) {
        a = getAlphaQuestionable(a, drawing);
    }

    color_out = mix(color_out, feature_color, a);

}
