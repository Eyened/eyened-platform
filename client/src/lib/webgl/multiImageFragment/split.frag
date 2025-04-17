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

uniform bool u_direction;
uniform float u_width;

void main() {

    vec3 color_primary = texture(u_primary, v_uv).rgb;
    vec3 color_secondary = texture(u_secondary, mapping(v_uv)).rgb;

    vec2 pointer_dist = u_pointer - u_image_size.xy * v_uv;
    float r;
    if(u_direction)
        r = pointer_dist.x;
    else
        r = pointer_dist.y;

    float d = smoothstep(-u_width, u_width, r);
    color_out.rgb = mix(color_secondary, color_primary, d);
    color_out.rgb = (255.0f * color_out.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0f;
}