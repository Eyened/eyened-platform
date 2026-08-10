#version 300 es
precision highp float;
precision highp sampler2DArray;

uniform sampler2DArray u_volume;
uniform vec3 u_image_size;
uniform int u_index;

layout(location = 0) out vec4 color_out;

void main() {
    vec2 uv = gl_FragCoord.xy / u_image_size.xy;
    // sampler2DArray layer index is not normalized (unlike sampler3D depth)
    float i = texture(u_volume, vec3(uv, float(u_index))).x;
    color_out = vec4(i, i, i, 1.0);
}
