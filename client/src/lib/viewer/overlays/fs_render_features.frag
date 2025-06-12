#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform mat3 u_transform;
uniform vec2 u_scale;
uniform vec3 u_image_size;

uniform usampler2D u_annotation;
uniform uint u_layer_bit;

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
	// diagonal bands
	// float bandWidth = 2.0f * u_scale.x;
	// float bandWidth = 4.0f;
	// vec2 fragCoord = gl_FragCoord.xy;
	// float p = fragCoord.x - fragCoord.y;
	// float brightness = 0.5f + 0.5f * sin(p / bandWidth);
	// if(layer_annotation)
	// 	return 0.5f * a + 0.5f * brightness;
	// else
	// 	return 0.5f * brightness;

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
void outline() {
	vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
	uvec2 layer = uvec2(u_layer_bit);
	ivec2 pos = ivec2(p);
	bvec2 t00 = greaterThan(texelFetch(u_annotation, pos, 0).rg & layer, uvec2(0u));
	bvec2 t10 = greaterThan(texelFetch(u_annotation, pos + ivec2(1, 0), 0).rg & layer, uvec2(0u));
	bvec2 t01 = greaterThan(texelFetch(u_annotation, pos + ivec2(0, 1), 0).rg & layer, uvec2(0u));
	bvec2 t11 = greaterThan(texelFetch(u_annotation, pos + ivec2(1, 1), 0).rg & layer, uvec2(0u));

	int sum_drawing = int(t00.x) + int(t10.x) + int(t01.x) + int(t11.x);
	int sum_questionable = int(t00.y) + int(t10.y) + int(t01.y) + int(t11.y);
	bool border = sum_drawing > 0 && sum_drawing < 4;
	

}
void main() {

	color_out = vec4(0.0f);

	bool drawing;
	bool questionable;

	if(u_smooth) {
		vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
		uvec2 layer = uvec2(u_layer_bit);
		ivec2 pos = ivec2(p);
		bvec2 t00 = greaterThan(texelFetch(u_annotation, pos, 0).rg & layer, uvec2(0u));
		bvec2 t10 = greaterThan(texelFetch(u_annotation, pos + ivec2(1, 0), 0).rg & layer, uvec2(0u));
		bvec2 t01 = greaterThan(texelFetch(u_annotation, pos + ivec2(0, 1), 0).rg & layer, uvec2(0u));
		bvec2 t11 = greaterThan(texelFetch(u_annotation, pos + ivec2(1, 1), 0).rg & layer, uvec2(0u));
		vec2 f = fract(p);
		vec2 u0 = mix(vec2(t00), vec2(t10), f.x);
		vec2 u1 = mix(vec2(t01), vec2(t11), f.x);
		vec2 u = mix(u0, u1, f.y);

		drawing = u.x > 0.5f;
		questionable = u.y > 0.5f;

	} else {
		uvec2 tex = texture(u_annotation, v_uv).rg;
		drawing = (u_layer_bit & tex.r) > 0u;
		questionable = (u_layer_bit & tex.g) > 0u;
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
