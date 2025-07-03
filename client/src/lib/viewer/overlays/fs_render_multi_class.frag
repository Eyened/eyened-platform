#version 300 es
precision highp usampler2D;
precision highp float;
precision highp int;

uniform usampler2D u_annotation;
uniform usampler2D u_boundaries;


uniform float u_alpha;
uniform vec3[32] u_colors;
uniform int u_highlighted_feature_index;
uniform vec3 u_image_size;

uniform bool u_smooth;
uniform usampler2D u_mask;
uniform uint u_mask_bitmask;
uniform bool u_has_mask;

in vec2 v_uv;

layout(location=0)out vec4 color_out;

float getAlphaQuestionable(float a,bool layer_annotation){
    float bandWidth=20.f;
    vec2 blockCoord=mod(gl_FragCoord.xy,bandWidth);
    float brightness=float((blockCoord.x<bandWidth*.5)!=(blockCoord.y<bandWidth*.5));
    return mix(.5f*brightness,.5f*(a+brightness),float(layer_annotation));
}

float bilinear(usampler2D binary_mask, uint bitmask, vec2 pos) {
    ivec2 ipos = ivec2(pos);
    bool t00 = (bitmask & texelFetch(binary_mask, ipos, 0).r) > 0u;
    bool t10 = (bitmask & texelFetch(binary_mask, ipos + ivec2(1, 0), 0).r) > 0u;
    bool t01 = (bitmask & texelFetch(binary_mask, ipos + ivec2(0, 1), 0).r) > 0u;
    bool t11 = (bitmask & texelFetch(binary_mask, ipos + ivec2(1, 1), 0).r) > 0u;

    vec2 f = fract(pos);
    float u0 = mix(float(t00), float(t10), f.x);
    float u1 = mix(float(t01), float(t11), f.x);
    float u = mix(u0, u1, f.y);
    return u;
}

bool getMask(usampler2D mask, uint bitmask, vec2 pos) {
    if(u_smooth) {
        return bilinear(mask, bitmask, pos) > 0.5f;
    } else {
        return (bitmask & texelFetch(mask, ivec2(pos), 0).r) > 0u;
    }
}

void main(){
    vec2 p = v_uv * u_image_size.xy - vec2(0.5f);
    if(u_has_mask) {
        if (!getMask(u_mask, u_mask_bitmask, p)) {
            discard;
        }
    }
    
    uint annotation = texture(u_annotation,v_uv).r;
    
    bool has_layer=annotation>0u;
    
    if(has_layer){
        // &31 = mod 32
        vec3 color=u_colors[(annotation-1u)&31u];
        // highlight layer if u_highlighted_feature_index is 0 (none specified) or if this is the highlighted layer
        float show_highlight=float(u_highlighted_feature_index==int(annotation));
        // 0.3f is the default alpha value, u_alpha is the alpha value for the highlight
        color_out=vec4(color,mix(.3f,u_alpha,show_highlight));
    }else{
        color_out=vec4(0.);
    }
    
    // 16 bit unsigned integer for boundary value in range 0-885
    // Red channel: top boundary
    // Green channel: bottom boundary
    
    if(has_layer){
        // ivec2 bounds_coord=ivec2(texCoord.x,int(annotation)-1);
        // uvec2 boundaries=texelFetch(u_boundaries,bounds_coord,0).rg;
        // float top_boundary=float(boundaries.r);
        // float bottom_boundary=float(boundaries.g);
        // float dist_top=texCoordFloat.y-top_boundary;
        // float dist_bottom=bottom_boundary-texCoordFloat.y + 1.f;
        // float dist=min(dist_top,dist_bottom);
        
        // float d=1.f-smoothstep(0.f,1.f,dist);
        // color_out.a=mix(color_out.a,1.f,d);
    }
    // if((annotation&u_questionable_bit)>0u){
    //     // apply block pattern to questionable regions
    //     color_out.a=getAlphaQuestionable(color_out.a,has_layer);
    // }
}