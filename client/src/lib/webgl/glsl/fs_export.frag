#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_annotation;
uniform uint u_bitmask;

layout(location = 0) out vec4 color_out;

void main() {
    
	uvec2 annotation = texelFetch(u_annotation, ivec2(gl_FragCoord.xy), 0).rg;
	
	bool annotation_present = (annotation.r & u_bitmask) > 0u;
	bool questionable_present = (annotation.g & u_bitmask) > 0u;
    
	color_out = vec4(0, 0, 0, 1);
	
	if (annotation_present) {
        color_out.r = 1.0;
    } 
	if (questionable_present) {
        color_out.g = 1.0;
    } 
}