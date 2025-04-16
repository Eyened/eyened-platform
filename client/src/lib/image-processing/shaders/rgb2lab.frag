#version 300 es
precision highp float;

// Input
uniform sampler2D u_image;
uniform vec2 u_resolution;

// Output
layout(location = 0) out vec4 outColor;

// Constants
const float t1 = 6.0f / 29.0f;
const float t2 = 3.0f * t1 * t1;
const float t3 = t1 * t1 * t1;

// Function to convert from standard RGB to linear RGB
float rgb2lrgb(float x2) {
    return x2 <= 0.04045f ? x2 / 12.92f : pow((x2 + 0.055f) / 1.055f, 2.4f);
}

// Function to convert from XYZ to LAB
float xyz2lab(float t) {
    return t > t3 ? pow(t, 1.0f / 3.0f) : t / t2 + 4.0f / 29.0f;
}

// Main function for RGB to LAB conversion
vec3 rgb2lab(vec3 rgb) {
    // Convert RGB to linear RGB
    float r = rgb2lrgb(rgb.r);
    float g = rgb2lrgb(rgb.g);
    float b = rgb2lrgb(rgb.b);

    // Compute XYZ values
    float y = xyz2lab((0.2225045f * r + 0.7168786f * g + 0.0606169f * b) / 1.0f);

    // If RGB values are equal, set x and z equal to y
    float x = (r == g && g == b) ? y : xyz2lab((0.4360747f * r + 0.3850649f * g + 0.1430804f * b) / 0.96422f);
    float z = (r == g && g == b) ? y : xyz2lab((0.0139322f * r + 0.0971045f * g + 0.7141733f * b) / 0.82521f);

    // Return the LAB values
    vec3 lab;
    lab.x = 116.0f * y - 16.0f;
    lab.y = 500.0f * (x - y);
    lab.z = 200.0f * (y - z);
    return lab;
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;

    vec3 rgb = texture(u_image, uv).rgb;
    vec3 lab = rgb2lab(rgb);

    // scales values to 0-1
    outColor = vec4(lab.r / 100.0f, 0.5f + lab.g / 256.0f, 0.5f + lab.b / 256.0f, 1.0f);
}
