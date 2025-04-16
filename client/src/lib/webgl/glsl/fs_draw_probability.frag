#version 300 es
precision highp float;

uniform bool u_erase;
uniform sampler2D u_source;
uniform float u_pressure;

out float out_value;

void main() {
    out_value = 1.0;
    return ;

    // vec2 p = gl_PointCoord - vec2(0.5f);
    // float r = length(p); //distance from center of point
    // float c = clamp(1.0f - r, 0.0f, 1.0f);
    // float a = 0.1f * u_pressure * c * c;

    // float source = texelFetch(u_source, ivec2(gl_FragCoord), 0).r;

    // float v_out;
    // if(u_erase) {
    //     v_out = pow(source, 1.0f / (1.0f - a));
    //     v_out = min(v_out, 0.99f);
    // } else {
    //     v_out = pow(source, 1.0f - a);
    //     v_out = max(v_out, 0.01f);
    // }
    // out_value = v_out;
}
