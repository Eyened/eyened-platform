import { describe, expect, it, vi } from "vitest";
import type { ImageGET } from "../../types/openapi_types";
import { createVolumeImage } from "./createVolumeImage";
import { Image3D } from "./image3D";
import { ImageSliceStack } from "./imageSliceStack";
import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";

const instance = { modality: "OCT", resolution_axial: 1 } as ImageGET;

function dimensions(depth: number): Dimensions {
    return {
        width: 2,
        height: 2,
        depth,
        width_mm: 1,
        height_mm: 1,
        depth_mm: 1,
    };
}

function fakeGl(max3d: number): WebGL2RenderingContext {
    const gl = {
        MAX_3D_TEXTURE_SIZE: 10,
        MAX_TEXTURE_SIZE: 11,
        MAX_ARRAY_TEXTURE_LAYERS: 12,
        getParameter(p: number) {
            return p === 10 ? max3d : 64;
        },
        createTexture: () => ({}),
        deleteTexture: () => {},
        bindTexture: () => {},
        texParameteri: () => {},
        texImage3D: () => {},
        canvas: { clientWidth: 1, clientHeight: 1 },
    };
    for (const name of [
        "TEXTURE_3D",
        "TEXTURE_2D_ARRAY",
        "TEXTURE_MIN_FILTER",
        "TEXTURE_MAG_FILTER",
        "TEXTURE_WRAP_S",
        "TEXTURE_WRAP_T",
        "TEXTURE_WRAP_R",
        "LINEAR",
        "CLAMP_TO_EDGE",
        "R8",
        "RED",
        "UNSIGNED_BYTE",
    ]) {
        (gl as Record<string, number>)[name] = name.length;
    }
    return gl as unknown as WebGL2RenderingContext;
}

function webgl(max3d: number): WebGL {
    return { gl: fakeGl(max3d) } as WebGL;
}

describe("OCTA flow volumes", () => {
    it("attaches flow on a 3D texture and again replaces it", () => {
        const data = new Uint8Array(8);
        const image = new Image3D(
            instance,
            webgl(64),
            "oct",
            data,
            dimensions(2),
            {},
            data,
        );
        expect(image.hasFlow).toBe(true);
        image.attachFlow(data);
        expect(() => image.attachFlow(new Uint8Array(1))).toThrow(/length/);
        image.dispose();
    });

    it("stores a volume that does not fit a 3D texture as a slice stack", () => {
        const data = new Uint8Array(2 * 2 * 8);
        const image = createVolumeImage(
            instance,
            webgl(4),
            "oct",
            data,
            dimensions(8),
            {},
            { flowData: data },
        );
        expect(image).toBeInstanceOf(ImageSliceStack);
        expect(image.hasFlow).toBe(true);
        image.attachFlow(data);
        expect(() => image.attachFlow(new Uint8Array(1))).toThrow(/length/);
        image.dispose();
    });

    it("stores a small volume as Image3D", () => {
        const data = new Uint8Array(8);
        const image = createVolumeImage(
            instance,
            webgl(64),
            "oct",
            data,
            dimensions(2),
            {},
            { flowData: null },
        );
        expect(image).toBeInstanceOf(Image3D);
        expect(image.hasFlow).toBe(false);
    });

    it("does not upload a flow texture after dispose", () => {
        const gl = fakeGl(64);
        const createTexture = vi.fn(() => ({}));
        gl.createTexture = createTexture;
        const data = new Uint8Array(8);
        const image = new Image3D(
            instance,
            { gl } as WebGL,
            "oct",
            data,
            dimensions(2),
            {},
        );
        createTexture.mockClear();
        image.dispose();
        image.attachFlow(data);
        expect(createTexture).not.toHaveBeenCalled();
        expect(image.flowAbort.signal.aborted).toBe(true);
    });
});
