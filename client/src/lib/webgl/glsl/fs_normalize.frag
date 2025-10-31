#version 300 es
precision highp float;

uniform sampler2D u_input;      // R32F summed values
uniform sampler2D u_minmax;     // RG32F texture containing min (R) and max (G) at (0,0)

out vec4 color; // RGBA8 target (0..1)

void main() {
    ivec2 loc = ivec2(gl_FragCoord.xy);
    float v = texelFetch(u_input, loc, 0).r;
    
    // Read min and max from the minmax texture at position (0,0)
    vec2 minmax = texelFetch(u_minmax, ivec2(0, 0), 0).rg;
    float u_min = minmax.x;
    float u_max = minmax.y;
    
    float denom = max(u_max - u_min, 1e-6);
    float n = clamp((v - u_min) / denom, 0.0, 1.0);
    color = vec4(vec3(n), 1.0);
}


