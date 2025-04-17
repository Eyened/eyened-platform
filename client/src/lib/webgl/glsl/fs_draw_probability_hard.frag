#version 300 es
precision highp float;

uniform sampler2D u_drawing;
uniform sampler2D u_current;

uniform bool u_questionable;
uniform bool u_paint;

layout(location = 0) out vec4 color_out;
void main() {
    
    float drawing = texelFetch(u_drawing, ivec2(gl_FragCoord.xy), 0).r;

    float val = texelFetch(u_current, ivec2(gl_FragCoord.xy), 0).r;

    if(drawing > 0.0f) {
        if(u_paint) {
            if(u_questionable)
                val = 0.75f;
            else
                val = 1.0f;

        } else {
            if(u_questionable)
                val = 0.25f;
            else
                val = 0.0f;
        }
    }
    color_out = vec4(val, 0, 0, 1);
}