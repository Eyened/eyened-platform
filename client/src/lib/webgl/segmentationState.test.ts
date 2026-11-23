import { afterEach, describe, expect, it, vi } from "vitest";
import { updateSegmentationData } from "$lib/data/helpers";
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
    const image = {
        image_id: "img",
        width: 2,
        height: 2,
        depth: 1,
    } as AbstractImage;
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

describe("SegmentationState.dispose", () => {
    it("sends the mask as it was at dispose, not the disposed mask", async () => {
        const state = await emptySliceState();
        const mask = state.mask as unknown as {
            exportData: () => Uint8Array;
            dispose: () => void;
        };
        let data = new Uint8Array([1, 1, 1, 1]);
        mask.exportData = () => data.slice();
        mask.dispose = () => {
            data = new Uint8Array(4);
        };
        const puts = vi.mocked(updateSegmentationData);
        let finishFirst!: () => void;
        puts.mockReset();
        puts.mockReturnValueOnce(
            new Promise((resolve) => {
                finishFirst = () =>
                    resolve({ json: async () => ({}) } as never);
            }),
        );
        puts.mockResolvedValue({ json: async () => ({}) } as never);

        await state.checkpoint();
        await vi.advanceTimersByTimeAsync(2000); // first PUT goes out and stays open
        data = new Uint8Array([2, 2, 2, 2]);
        await state.checkpoint(); // newer edit waits behind the open PUT
        state.dispose();
        finishFirst();
        await vi.advanceTimersByTimeAsync(0);

        expect(puts).toHaveBeenCalledTimes(2);
        // The .npy payload ends with the four mask bytes.
        const sent = new Uint8Array(puts.mock.calls[1][1] as ArrayBuffer);
        expect(Array.from(sent.slice(-4))).toEqual([2, 2, 2, 2]);
    });
});
