import { afterEach, describe, expect, it, vi } from "vitest";
import type { SegmentationGET } from "../../types/openapi_types";
import type { AbstractImage } from "./abstractImage";
import type { Mask } from "./mask.svelte";
import { constructors, SegmentationState } from "./segmentationState.svelte";

vi.mock("$lib/data/helpers", () => ({
    getSegmentationData: vi.fn().mockResolvedValue(null),
    getModelSegmentationData: vi.fn().mockResolvedValue(null),
    updateSegmentationData: vi.fn(),
}));
vi.mock("./imageEncoder", () => ({
    Base64Serializer: class {
        serialize() {
            return "";
        }
    },
}));

const realBinary = constructors.Binary;

function fakeMask(): Mask {
    return {
        planeWidth: 2,
        planeHeight: 2,
        exportData: () => new Uint8Array(4),
        importData: vi.fn(),
        draw: vi.fn(),
    } as unknown as Mask;
}

afterEach(() => {
    constructors.Binary = realBinary;
    vi.useRealTimers();
});

async function emptySliceState() {
    vi.useFakeTimers();
    constructors.Binary = function () {
        return fakeMask();
    } as never;
    const segmentation = {
        id: 1,
        annotation_type: "segmentation",
        data_representation: "Binary",
        data_type: "R8",
        width: 2,
        height: 2,
    } as unknown as SegmentationGET;
    const image = { width: 2, height: 2, depth: 1 } as AbstractImage;
    const state = new SegmentationState(image, segmentation, 0);
    await state.loaded;
    expect(state.isEmptyForSlice).toBe(true);
    return state;
}

describe("SegmentationState.isEmptyForSlice", () => {
    it("draw clears the flag the server's empty answer set", async () => {
        const state = await emptySliceState();
        await state.draw({} as HTMLCanvasElement, {} as never);
        expect(state.isEmptyForSlice).toBe(false);
    });

    it("importOther clears the flag the server's empty answer set", async () => {
        const state = await emptySliceState();
        await state.importOther({
            exportData: () => new Uint8Array(4),
            planeWidth: 2,
            planeHeight: 2,
            segmentation: {
                data_representation: "Binary",
                image_projection_matrix: null,
                threshold: 0.5,
            },
        } as unknown as Mask);
        expect(state.isEmptyForSlice).toBe(false);
    });
});
