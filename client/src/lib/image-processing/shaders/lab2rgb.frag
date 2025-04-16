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

// Function to convert from linear RGB to standard RGB (gamma correction)
float lrgb2rgb(float x) {
    return round(255.0f * (x <= 0.0031308f ? 12.92f * x : 1.055f * pow(x, 1.0f / 2.4f) - 0.055f));
}

// Function to convert from LAB space to XYZ space
float lab2xyz(float t) {
    return t > t1 ? pow(t, 3.0f) : t2 * (t - 4.0f / 29.0f);
}

// Main conversion function from LAB to RGB
vec3 lab2rgb(vec3 lab) {
    float luminance = lab.x;
    float a = lab.y;
    float b = lab.z;

    // Compute base Y
    float baseY = (luminance + 16.0f) / 116.0f;

    // Convert to XYZ space
    float x = 0.96422f * lab2xyz(baseY + a / 500.0f);
    float y = lab2xyz(baseY);
    float z = 0.82521f * lab2xyz(baseY - b / 200.0f);

    // Convert to RGB space
    float red = lrgb2rgb(3.1338561f * x - 1.6168667f * y - 0.4906146f * z);
    float green = lrgb2rgb(-0.9787684f * x + 1.9161415f * y + 0.0334540f * z);
    float blue = lrgb2rgb(0.0719453f * x - 0.2289914f * y + 1.4052427f * z);

    // Return the resulting RGB color
    return vec3(red, green, blue);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 lab01 = texture(u_image, uv).rgb;
    vec3 lab = vec3(lab01.r * 100.0f, lab01.g * 256.0f - 128.0f, lab01.b * 256.0f - 128.0f);
    vec3 rgb255 = lab2rgb(lab);

    outColor = vec4(rgb255 / 255.0f, 1.0f);

}
