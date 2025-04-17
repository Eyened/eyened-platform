#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_source;
uniform sampler2D u_blur;
uniform vec2 u_resolution;
uniform float u_contrast;
uniform bool u_sharpen;
layout(location = 0) out vec4 ce;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec4 blurred = texture(u_blur, uv);
    vec4 source = texture(u_source, uv);

    if(u_sharpen) {
        ce = source + u_contrast * (source - blurred);
    } else {
        ce = vec4(0.5f) + u_contrast * (source - blurred);
    }

    ce.a = 1.0f;
}