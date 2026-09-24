import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GlobalContext } from "$lib/data/globalContext.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { ModelSegmentationGET } from "../../../types/openapi_types";
import { duplicate } from "./duplicate_utils";

vi.mock("$lib/data/api", () => ({
    createSegmentation: vi.fn(async (item: unknown) => item),
}));

const { createSegmentation } = await import("$lib/data/api");

const matrix = [
    [2, 0, 0],
    [0, 2, 0],
    [0, 0, 1],
];

function modelSegmentation(
    overrides: Partial<ModelSegmentationGET> = {},
): ModelSegmentationGET {
    return {
        id: 7,
        annotation_type: "model_segmentation",
        image_id: "img-1",
        depth: 1,
        height: 4,
        width: 4,
        sparse_axis: 0,
        image_projection_matrix: matrix,
        scan_indices: null,
        threshold: 0.5,
        data_type: "R8UI",
        data_representation: "Binary",
        feature: { id: 3 },
        ...overrides,
    } as ModelSegmentationGET;
}

function image(overrides: Partial<AbstractImage> = {}): AbstractImage {
    return {
        image_id: "img-1",
        height: 6,
        width: 10,
        depth: 1,
        is3D: false,
        ...overrides,
    } as AbstractImage;
}

function segmentationItem(planes: Uint8Array[]): SegmentationItem {
    return {
        getMask: (scanNr: number) => ({
            exportData: () => planes[scanNr],
        }),
    } as unknown as SegmentationItem;
}

async function copy(
    segmentation: ModelSegmentationGET,
    source: AbstractImage,
    item: SegmentationItem,
    duplicateVolume = false,
) {
    return duplicate(
        { dialogue: null } as GlobalContext,
        segmentation,
        item,
        source,
        { index: 0 } as ViewerContext,
        duplicateVolume,
        "B",
        0.5,
        0.5,
    );
}

describe("duplicate", () => {
    beforeEach(() => {
        vi.mocked(createSegmentation).mockClear();
    });

    it("posts the model grid when the image is a different size", async () => {
        const plane = Uint8Array.from([
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
        ]);
        const segmentation = modelSegmentation();

        await copy(segmentation, image(), segmentationItem([plane]));

        expect(createSegmentation).toHaveBeenCalledOnce();
        const [posted, array] = vi.mocked(createSegmentation).mock.calls[0];
        expect(posted).toMatchObject({
            depth: 1,
            height: 4,
            width: 4,
            image_projection_matrix: matrix,
        });
        expect(array.shape).toEqual([1, 4, 4]);
        expect(Array.from(array.data)).toEqual(Array.from(plane));
    });

    it("keeps the image grid when the segmentation already matches it", async () => {
        const plane = Uint8Array.from([1, 2, 3, 4]);
        const segmentation = modelSegmentation({
            height: 2,
            width: 2,
            image_projection_matrix: null,
        });

        await copy(
            segmentation,
            image({ height: 2, width: 2 }),
            segmentationItem([plane]),
        );

        const [posted, array] = vi.mocked(createSegmentation).mock.calls[0];
        expect(posted).toMatchObject({ depth: 1, height: 2, width: 2 });
        expect(array.shape).toEqual([1, 2, 2]);
        expect(Array.from(array.data)).toEqual(Array.from(plane));
    });

    it("places each slice on the model grid when duplicating a volume", async () => {
        const first = Uint8Array.from([1, 2, 3, 4, 5, 6]);
        const second = Uint8Array.from([7, 8, 9, 10, 11, 12]);
        const segmentation = modelSegmentation({
            depth: 2,
            height: 2,
            width: 3,
        });

        await copy(
            segmentation,
            image({ height: 5, width: 7, depth: 2 }),
            segmentationItem([first, second]),
            true,
        );

        const [, array] = vi.mocked(createSegmentation).mock.calls[0];
        expect(array.shape).toEqual([2, 2, 3]);
        expect(Array.from(array.data)).toEqual([...first, ...second]);
    });
});
