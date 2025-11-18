#version 300 es
precision highp float;
precision highp sampler3D;

uniform sampler3D u_volume;
uniform vec3 u_image_size;
uniform int u_index;

layout(location = 0) out vec4 color_out;

void main() {
    // Calculate UV coordinates from fragment position
    vec2 uv = gl_FragCoord.xy / u_image_size.xy;
    
    // Sample the 3D texture at the specified slice index
    vec3 uvw = vec3(uv, (float(u_index) + 0.5) / u_image_size.z);
    float i = texture(u_volume, uvw).x;
    
    // Convert to RGBA (grayscale)
    color_out = vec4(i, i, i, 1.0);
}

