#version 300 es
precision highp usampler2D;
precision highp int;

uniform usampler2D u_drawing;
uniform usampler2D u_current;
uniform uint u_questionable_bit;
uniform uint u_featureValue;

layout(location = 0) out uint color_out;

ivec2 offsets[4] = ivec2[4](ivec2(1, 0),   // Right neighbor
ivec2(0, 1),   // Bottom neighbor
ivec2(-1, 0),  // Left neighbor
ivec2(0, -1)   // Top neighbor
);

bool withinBounds(ivec2 pos, ivec2 size) {
    return pos.x >= 0 && pos.x < size.x && pos.y >= 0 && pos.y < size.y;
}

void main() {
    ivec2 pos = ivec2(gl_FragCoord.xy);
    uvec2 pix = texelFetch(u_drawing, pos, 0).xy;
    color_out = texelFetch(u_current, pos, 0).r;
    bool hasDrawing = (color_out & ~u_questionable_bit) == u_featureValue;
    uint current_questionable = color_out & u_questionable_bit;

    ivec2 textureSize = textureSize(u_current, 0).xy;  // Precompute texture size

    if(pix.x > 0u) {
        // Dilation
        if(!hasDrawing) {
            for(int i = 0; i < 4; i++) {
                ivec2 offset = offsets[i];
                ivec2 neighborPos = pos + offset;

                if(withinBounds(neighborPos, textureSize)) {
                    uint neighbor = texelFetch(u_current, neighborPos, 0).r & ~u_questionable_bit;

                    if(neighbor == u_featureValue) {
                        color_out = u_featureValue | current_questionable;
                        break;  // No need to check remaining neighbors
                    }
                }
            }
        }
    }

    if(pix.y > 0u) {
        // Erosion
        if(hasDrawing) {
            bool erode = false;
            uint neighbor = 0u;
            for(int i = 0; i < 4; i++) {
                ivec2 offset = offsets[i];
                ivec2 neighborPos = pos + offset;

                if(withinBounds(neighborPos, textureSize)) {
                    neighbor = texelFetch(u_current, neighborPos, 0).r & ~u_questionable_bit;

                    if(neighbor != u_featureValue) {
                        //pixel is on edge of drawing
                        erode = true;
                        break;  
                        // // check oppoiste neighbor

                        // ivec2 oppositeNeighborPos = pos - offset;
                        // if(withinBounds(oppositeNeighborPos, textureSize)){
                        //     uint oppositeNeighbor = texelFetch(u_current, oppositeNeighborPos, 0).r & ~u_questionable_bit;

                        //     // only erode if this is not the last pixel    
                        //     if(oppositeNeighbor == u_featureValue) {
                        //         erode = true;
                        //         break;
                        //     }
                        // }                        

                    }
                }
            }

            if(erode) {
                color_out = neighbor;
            }
        }
    }
}