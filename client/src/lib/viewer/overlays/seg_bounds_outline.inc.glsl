// Requires: uniform bool u_show_seg_bounds; in vec2 v_uv;

bool isSegPlaneOutlineScreen() {
    if (!u_show_seg_bounds) {
        return false;
    }
    float edgeDist = min(min(v_uv.x, 1.0 - v_uv.x), min(v_uv.y, 1.0 - v_uv.y));
    float uvPerPixel = max(fwidth(v_uv.x), fwidth(v_uv.y));
    return edgeDist < uvPerPixel;
}

vec4 segPlaneOutlineColor() {
    return vec4(0.78, 0.78, 0.78, 0.38);
}

void applySegPlaneOutline(inout vec4 color) {
    if (!isSegPlaneOutlineScreen()) {
        return;
    }
    vec4 outline = segPlaneOutlineColor();
    color = mix(color, outline, outline.a);
}
