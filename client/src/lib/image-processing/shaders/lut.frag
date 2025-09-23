#version 300 es
precision highp float;
precision highp sampler2D;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;
uniform vec3[256] u_lut;

layout(location = 0) out vec4 color_out;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 source = texture(u_source, uv).rgb;

    color_out.r = u_lut[int(255.0 * source.r)].r;
    color_out.g = u_lut[int(255.0 * source.g)].g;
    color_out.b = u_lut[int(255.0 * source.b)].b;
    color_out.a = 1.0;
}