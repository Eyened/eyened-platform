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

void main() {

    vec3 color_primary = texture(u_primary, v_uv).rgb;    
    vec3 color_secondary = texture(u_secondary, mapping(v_uv)).rgb;
    
    color_out.rgb = mix(color_primary, color_secondary, u_blend);
    color_out.rgb = (255.0 * color_out.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}