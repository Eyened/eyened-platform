import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImageGET } from "../../types/openapi_types";

const { attachFlow, volumeKind } = vi.hoisted(() => ({
    attachFlow: vi.fn(),
    volumeKind: { current: "3d" as "3d" | "2d" },
}));

vi.mock("$lib/webgl/image3D", () => ({
    Image3D: class Image3D {
        image_id = "vol";
        width = 2;
        height = 2;
        depth = 2;
        orientation = "coronal";
        attachFlow = attachFlow;
    },
}));

vi.mock("$lib/webgl/image2D", () => ({
    Image2D: class Image2D {},
}));

vi.mock("$lib/webgl/imageSliceStack", () => ({
    ImageSliceStack: class ImageSliceStack {},
}));

vi.mock("$lib/webgl/createVolumeImage", async () => {
    const { Image3D } = await import("$lib/webgl/image3D");
    const { Image2D } = await import("$lib/webgl/image2D");
    return {
        createVolumeImage: () =>
            volumeKind.current === "2d" ? new Image2D() : new Image3D(),
    };
});

const decodeDicomBuffer = vi.fn();

vi.mock("./dicomDecoder", () => ({
    decodeDicomBuffer: (...args: unknown[]) => decodeDicomBuffer(...args),
}));

function instance(role: string | null): ImageGET {
    return {
        id: "img-1",
        data_format: "dicom",
        rows: 2,
        columns: 2,
        nr_of_frames: 2,
        storages: [
            { id: 1, format: "dicom", is_primary: true, role: null },
            { id: 9, format: "dicom", is_primary: false, role },
        ],
    } as ImageGET;
}

function volume(length: number, depth = 2) {
    return {
        volume: new Uint8Array(length),
        dimensions: { width: 2, height: 2, depth },
        meta: {},
    };
}

describe("ImageLoader OCTA", () => {
    beforeEach(() => {
        attachFlow.mockReset();
        decodeDicomBuffer.mockReset();
        volumeKind.current = "3d";
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => ({
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8),
            })),
        );
    });

    it("loads structural first and attaches a matching flow volume", async () => {
        decodeDicomBuffer
            .mockResolvedValueOnce(volume(8))
            .mockResolvedValueOnce(volume(8));
        const { ImageLoader } = await import("./imageLoader");
        const progress = { loading: { message: "" }, onFlowReady: vi.fn() };
        const loaded = await new ImageLoader({} as never).load(
            instance("angio_flow"),
            progress,
        );
        expect(loaded).toHaveLength(1);
        expect(progress.loading.message).toBe("Decoding…");
        await vi.waitFor(() => expect(attachFlow).toHaveBeenCalledOnce());
        expect(progress.onFlowReady).toHaveBeenCalledWith("img-1");
    });

    it("skips flow when the structural buffer is not a mono volume", async () => {
        decodeDicomBuffer.mockResolvedValueOnce(volume(3));
        const { ImageLoader } = await import("./imageLoader");
        const loaded = await new ImageLoader({} as never).load(
            instance("angio_flow"),
        );
        expect(loaded).toHaveLength(1);
        expect(attachFlow).not.toHaveBeenCalled();
    });

    it("does not fetch flow when structural is not a volume", async () => {
        volumeKind.current = "2d";
        decodeDicomBuffer.mockResolvedValueOnce(volume(8));
        const { ImageLoader } = await import("./imageLoader");
        const loaded = await new ImageLoader({} as never).load(
            instance("angio_flow"),
        );
        expect(loaded).toHaveLength(1);
        expect(decodeDicomBuffer).toHaveBeenCalledOnce();
        expect(attachFlow).not.toHaveBeenCalled();
    });

    it("keeps structural when flow length does not match", async () => {
        decodeDicomBuffer
            .mockResolvedValueOnce(volume(8))
            .mockResolvedValueOnce(volume(4));
        const { ImageLoader } = await import("./imageLoader");
        await new ImageLoader({} as never).load(instance("angio_flow"));
        await vi.waitFor(() =>
            expect(decodeDicomBuffer).toHaveBeenCalledTimes(2),
        );
        expect(attachFlow).not.toHaveBeenCalled();
    });

    it("keeps structural when flow does not match", async () => {
        decodeDicomBuffer
            .mockResolvedValueOnce(volume(8))
            .mockResolvedValueOnce(volume(1, 1));
        const { ImageLoader } = await import("./imageLoader");
        await new ImageLoader({} as never).load(instance("angio_flow"));
        await vi.waitFor(() =>
            expect(decodeDicomBuffer).toHaveBeenCalledTimes(2),
        );
        expect(attachFlow).not.toHaveBeenCalled();
    });

    it("loads a structural DICOM when no flow role is present", async () => {
        decodeDicomBuffer.mockResolvedValueOnce(volume(8));
        const { ImageLoader } = await import("./imageLoader");
        const loaded = await new ImageLoader({} as never).load(instance(null));
        expect(loaded).toHaveLength(1);
        expect(decodeDicomBuffer).toHaveBeenCalledOnce();
    });

    it("reports a failed DICOM download", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => ({ ok: false, status: 404 })),
        );
        const { ImageLoader } = await import("./imageLoader");
        await expect(
            new ImageLoader({} as never).load(instance(null)),
        ).rejects.toThrow(/404/);
    });
});
