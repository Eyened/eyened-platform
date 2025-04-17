#version 300 es
precision highp float;
precision highp sampler2D;

uniform sampler2D u_source;
uniform vec2 u_resolution;
uniform vec4 u_ROIrect;
uniform vec3 u_ROIcircle;

layout(location = 0) out vec4 mirrored;

vec2 mirrorInDisk(vec2 pos, vec2 center, float radius, float r_margin) {
    vec2 diff = pos - center;
    float r = length(diff);
    float th = atan(diff.y, diff.x);
    float d = r - radius + r_margin;
    float r2 = radius - r_margin - d;

    if(d >= 0.0f) {
        return center + vec2(cos(th), sin(th)) * r2;
    } else {
        return pos;
    }
}

vec2 mirrorInBox(vec2 pos, vec4 box, float r_margin) {
    float min_x = box.x + r_margin;
    float min_y = box.y + r_margin;
    float max_x = box.z - r_margin;
    float max_y = box.w - r_margin;

    if(pos.x < min_x) {
        pos.x = min_x + (min_x - pos.x);
    } else if(pos.x > max_x) {
        pos.x = max_x - (pos.x - max_x);
    }

    if(pos.y < min_y) {
        pos.y = min_y + (min_y - pos.y);
    } else if(pos.y > max_y) {
        pos.y = max_y - (pos.y - max_y);
    }

    return pos;
}

void main() {
    vec2 pos = gl_FragCoord.xy;
    vec2 center = u_ROIcircle.xy;
    float radius = u_ROIcircle.z;
    float r_margin = 4.0f;

    vec2 diskMirroredPos = mirrorInDisk(pos, center, radius, r_margin);
    vec2 finalPos = diskMirroredPos;

    bool insideDisk = length(diskMirroredPos - center) <= radius;

    float min_x = u_ROIrect.x + r_margin;
    float min_y = u_ROIrect.y + r_margin;
    float max_x = u_ROIrect.z - r_margin;
    float max_y = u_ROIrect.w - r_margin;
    bool insideBox = finalPos.x > min_x && finalPos.x < max_x && finalPos.y > min_y && finalPos.y < max_y;

    if(insideDisk && !insideBox) {
        finalPos = mirrorInBox(diskMirroredPos, u_ROIrect, r_margin);
    }

    vec2 samplePosUV = clamp(finalPos / u_resolution, 0.0f, 1.0f);

    mirrored = texture(u_source, samplePosUV);
}