#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;
uniform vec2 u_dir;

uniform float u_weights[256];
uniform int u_kernelSize;

layout(location = 0) out vec4 blurred;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec2 d = u_dir / u_resolution;
    blurred = texture(u_source, uv) * u_weights[0];
    for(int i = 1; i < u_kernelSize; i++) {
        blurred += texture(u_source, uv + float(i) * d) * u_weights[i];
        blurred += texture(u_source, uv - float(i) * d) * u_weights[i];
    }
}