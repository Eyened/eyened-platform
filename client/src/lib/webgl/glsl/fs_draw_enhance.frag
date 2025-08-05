#version 300 es
precision highp sampler2D;
precision highp int;
precision highp float;

uniform sampler2D u_current;  // Current texture containing values
uniform vec2 u_position;      // Position of the brush on the texture
uniform bool u_erase;         // Whether we are erasing (decreasing value)
uniform float u_hardness;     // Brush hardness (controls falloff)
uniform float u_pressure;     // Brush pressure (strength of the effect)
uniform float u_radius;       // Brush radius
uniform float u_aspectRatio;  // Aspect ratio of the viewer

layout(location = 0) out vec4 color_out;

void main() {
    // Fetch current value at the fragment
    float current = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).r;

    // Calculate distance from brush center
    vec2 diff = (u_position - gl_FragCoord.xy) / vec2(1.0f, u_aspectRatio);
    float dist = length(diff);

    // Normalize the distance with the radius
    float r = dist / u_radius;

    // Only affect fragments within the brush radius
    if(r < 1.0f) {
        float target;

        float f = 0.1f;
        if(u_erase) {
            target = mix(current, 0.0f, f);
        } else {
            target = mix(current, 1.0f, f);
        }

        // Adjust the falloff based on hardness - higher hardness means sharper edge
        float falloff = pow(r, mix(1.0f, 10.0f, u_hardness));

        // Blend the target and current values using both falloff and pressure
        float blended_value = mix(target, current, falloff);

        // Final mix with pressure controlling the influence
        current = mix(blended_value, current, 1.0f - u_pressure);
    }

    // Output the final color with modified value in the red channel
    color_out = vec4(current, 0.0f, 0.0f, 1.0f);
}
