#version 300 es
precision highp usampler3D;
uniform usampler3D u_layers;
uniform uint u_depth;
uniform uint u_boundary;

layout(location = 0) out uvec2 boundary;

void main() {
    uint min_boundary = u_depth;
    uint max_boundary = 0u;
    for(uint i = 0u; i < u_depth; i++) {
        ivec3 p = ivec3(gl_FragCoord.x, i, gl_FragCoord.y);
        uint v = texelFetch(u_layers, p, 0).r;
        if(v == u_boundary) {
            min_boundary = min(min_boundary, i);
            max_boundary = max(max_boundary, i);
        }
    }
    boundary = uvec2(min_boundary, max_boundary);
}