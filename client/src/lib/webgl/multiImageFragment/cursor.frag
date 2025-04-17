#version 300 es
precision highp float;

uniform vec2 u_translate;
uniform vec2 u_scale;
uniform vec3 u_image_size;
uniform vec2 u_viewer_size;

uniform sampler2D u_primary;
uniform vec2 u_size_primary;

uniform sampler2D u_secondary;
uniform vec2 u_size_secondary;

uniform vec2 u_window_level;
uniform float u_blend;
uniform vec2 u_pointer;
in vec2 v_uv;

layout(location = 0) out vec4 color_out;

// @insert mapping
uniform float u_radius;

void main() {

    vec3 color_primary = texture(u_primary, v_uv).rgb;
    vec3 color_secondary = color_secondary_1();

    float pointer_dist = length(vec2(u_scale.x / u_scale.y, 1.0f) * (u_pointer - u_image_size.xy * v_uv));

    float r = u_radius;
    float dr = 1.0;
    float d = smoothstep(r, r + dr, pointer_dist);
    color_out.rgb = mix(color_secondary, color_primary, d);

    float dist_from_border = pointer_dist - r;
    float bell = exp(-(0.5/dr) * pow(dist_from_border, 2.0));

    color_out.rgb *= 1.0 - 0.2 * bell;


    color_out.rgb = (255.0f * color_out.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);

    color_out.a = 1.0f;
}