#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_annotation;
uniform usampler2D u_questionable;
uniform uint u_annotation_bitmask;
uniform uint u_questionable_bitmask;

layout(location = 0) out vec4 color_out;
void main() {
    
	
	uint annotation = texelFetch(u_annotation, ivec2(gl_FragCoord.xy), 0).r;
	uint questionable = texelFetch(u_questionable, ivec2(gl_FragCoord.xy), 0).r;
	
	bool annotation_present = (annotation & u_annotation_bitmask) > 0u;
	bool questionable_present = (questionable & u_questionable_bitmask) > 0u;
    
	color_out = vec4(0, 0, 0, 1);
	
	if (annotation_present) {
        color_out.r = 1.0;
    } 
	if (questionable_present) {
        color_out.g = 1.0;
    } 
}