#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;

uniform vec3 u_mean;
uniform vec3 u_std;

layout(location = 0) out vec4 color_out;

// target values: https://tvst.arvojournals.org/article.aspx?articleid=2610947
// red brightness = 192, green brightness = 96, blue brightness = 32; red span = 128, green span = 128, blue span = 32

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 source = 255.0 * texture(u_source, uv).rgb;
    vec3 alpha = vec3(128, 128, 32) / (4.0 * u_std);
    
    color_out.rgb = (vec3(192, 96, 32) + alpha * (source - u_mean)) / 255.0;
    color_out.a = 1.0;
}