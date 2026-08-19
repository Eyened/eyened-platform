#version 300 es
precision highp usampler2D;
precision highp float;

uniform usampler2D u_current;
uniform uint u_active_feature; // bit flags for multi-label, class index for multi-class

uniform sampler2D u_drawing;
uniform bool u_dilate;         // true: grow active feature, false: shrink it
uniform bool u_is_multi_label; // false for multi-class (integer class per pixel)

layout(location = 0) out uint out_value;

const ivec2 NEIGHBOR_OFFSETS[4] = ivec2[4](
    ivec2(1, 0),
    ivec2(0, 1),
    ivec2(-1, 0),
    ivec2(0, -1)
);

bool withinBounds(ivec2 pos) {
    ivec2 size = textureSize(u_current, 0).xy;
    return pos.x >= 0 && pos.x < size.x && pos.y >= 0 && pos.y < size.y;
}

uint getPixel(ivec2 pos) {
    return texelFetch(u_current, pos, 0).r;
}

void set_feature_bit() {
    out_value |= u_active_feature;
}

void clear_feature_bit() {
    out_value &= ~u_active_feature;
}

void dilate_bitmask(ivec2 pos) {
    for (int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + NEIGHBOR_OFFSETS[i];
        if (!withinBounds(neighborPos)) {
            continue;
        }
        if ((getPixel(neighborPos) & u_active_feature) > 0u) {
            set_feature_bit();
            return;
        }
    }
}

void erode_bitmask(ivec2 pos) {
    for (int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + NEIGHBOR_OFFSETS[i];
        if (!withinBounds(neighborPos)) {
            continue;
        }
        if ((getPixel(neighborPos) & u_active_feature) == 0u) {
            clear_feature_bit();
            return;
        }
    }
}

void dilate_class(ivec2 pos) {
    if (out_value == u_active_feature) {
        return;
    }
    for (int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + NEIGHBOR_OFFSETS[i];
        if (!withinBounds(neighborPos)) {
            continue;
        }
        if (getPixel(neighborPos) == u_active_feature) {
            out_value = u_active_feature;
            return;
        }
    }
}

void erode_class(ivec2 pos) {
    if (out_value != u_active_feature) {
        return;
    }
    for (int i = 0; i < 4; i++) {
        ivec2 neighborPos = pos + NEIGHBOR_OFFSETS[i];
        if (!withinBounds(neighborPos)) {
            continue;
        }
        uint neighborClass = getPixel(neighborPos);
        if (neighborClass != u_active_feature) {
            out_value = neighborClass;
            return;
        }
    }
}

void apply_morphology(ivec2 coord) {
    if (u_is_multi_label) {
        if (u_dilate) {
            dilate_bitmask(coord);
        } else {
            erode_bitmask(coord);
        }
    } else if (u_dilate) {
        dilate_class(coord);
    } else {
        erode_class(coord);
    }
}

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    out_value = getPixel(coord);
    bool under_brush = texelFetch(u_drawing, coord, 0).r > 0.0;

    if (under_brush) {
        apply_morphology(coord);
    }
}
