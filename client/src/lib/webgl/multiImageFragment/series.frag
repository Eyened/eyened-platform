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
uniform int u_n_images;

void main() {

    vec3 colors[5];
    colors[0] = texture(u_primary, v_uv).rgb;
    colors[1] = color_secondary_1();
    colors[2] = color_secondary_2();
    colors[3] = color_secondary_3();
    colors[4] = color_secondary_4();
    
    vec3 color_mix = colors[0];
    float f = u_blend * float(u_n_images - 1);
    int p = int(floor(f));
    int s = min(int(ceil(f)), u_n_images - 1);
    color_mix = mix(colors[p], colors[s], fract(f));
    
    color_out.rgb = (255.0 * color_mix.rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;  
}