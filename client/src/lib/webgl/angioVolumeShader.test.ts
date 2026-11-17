import { describe, expect, it } from "vitest";
import fs_renderImage3D from "./glsl/fs_render_image3D.frag";
import fs_renderSliceArray from "./glsl/fs_render_slice_array.frag";

describe("angio-aware volume shaders", () => {
    it("3D shader samples both volumes and branches on u_angio_mode", () => {
        expect(fs_renderImage3D).toContain("sampler3D u_image");
        expect(fs_renderImage3D).toContain("sampler3D u_flow");
        expect(fs_renderImage3D).toContain("u_angio_mode");
        expect(fs_renderImage3D).toContain(
            "mix(base, vec3(1.0f, 0.0f, 0.0f), f)",
        );
    });

    it("slice-array shader mirrors angio modes", () => {
        expect(fs_renderSliceArray).toContain("sampler2DArray u_flow");
        expect(fs_renderSliceArray).toContain("u_angio_mode == 1");
        expect(fs_renderSliceArray).toContain("u_angio_mode == 2");
    });
});
