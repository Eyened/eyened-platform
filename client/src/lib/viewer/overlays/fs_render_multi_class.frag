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

in vec2 v_uv;

layout(location=0)out vec4 color_out;

float getAlphaQuestionable(float a,bool layer_annotation){
    float bandWidth=20.f;
    vec2 blockCoord=mod(gl_FragCoord.xy,bandWidth);
    float brightness=float((blockCoord.x<bandWidth*.5)!=(blockCoord.y<bandWidth*.5));
    return mix(.5f*brightness,.5f*(a+brightness),float(layer_annotation));
}

void main(){
    // v_uv: width, height, depth
    vec2 texCoordFloat=v_uv*u_image_size.xy;
    ivec2 texCoord=ivec2(texCoordFloat);
    uint annotation=texelFetch(u_annotation,texCoord,0).r;
    
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