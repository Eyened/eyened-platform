import { afterEach, describe, expect, it } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import {
    aiGrid,
    gridBinding,
    GridLayers,
    keepGridSize,
} from "./gridLayers.svelte";

const SCHEMA_NAME = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;

afterEach(() => {
    formAnnotations.clear();
    formSchemasByName.delete(SCHEMA_NAME);
});

/** A synthetic ETDRS grid. */
function grid(
    id: number,
    creatorId: number,
    imageId: string,
    form_data: object = {},
): FormAnnotationGET {
    return {
        id,
        form_schema_id: 3,
        image_id: imageId,
        creator: { id: creatorId, name: `Grader ${creatorId}` },
        form_data,
    } as unknown as FormAnnotationGET;
}

describe("aiGrid", () => {
    it("is undefined when the model gave only one keypoint", () => {
        const image = (cf_keypoints: unknown) =>
            ({ image_id: "inst-1", instance: { cf_keypoints } }) as never;
        expect(
            aiGrid(image({ fovea_xy: [10, 11], disc_edge_xy: null })),
        ).toBeUndefined();
        expect(
            aiGrid(image({ fovea_xy: null, disc_edge_xy: [20, 21] })),
        ).toBeUndefined();
    });
});

describe("gridBinding", () => {
    it("names the grid Place ETDRS writes, or says why it can't: none, another grader's, another image", () => {
        const bind = (g?: FormAnnotationGET) =>
            gridBinding({
                grid: g,
                instanceId: "inst-1",
                userId: 5,
                canEdit: (a) => a.creator.id === 5,
            });
        expect(bind()).toEqual({
            name: null,
            reason: "No current grid. Choose one in ETDRS grids.",
        });
        expect(bind(grid(9, 7, "inst-1"))).toEqual({
            name: "Grader 7's grid 9",
            reason: "Another grader's grid can't be edited.",
        });
        expect(bind(grid(7, 5, "inst-2"))).toEqual({
            name: "Your grid 7",
            reason: "This grid is on another image.",
        });
        expect(bind(grid(12, 5, "inst-1"))).toEqual({
            name: "Your grid 12",
            reason: null,
        });
    });
});

describe("keepGridSize", () => {
    it("a moved fovea takes the disc edge along; a moved disc edge or a missing point moves nothing else", () => {
        const f = { x: 10, y: 10 };
        const d = { x: 40, y: 10 };
        expect(keepGridSize([f, d], [{ x: 15, y: 20 }, d])).toEqual([
            { x: 15, y: 20 },
            { x: 45, y: 20 },
        ]);
        expect(keepGridSize([f, d], [f, { x: 50, y: 10 }])).toEqual([
            f,
            { x: 50, y: 10 },
        ]);
        expect(keepGridSize([null, d], [{ x: 15, y: 20 }, d])).toEqual([
            { x: 15, y: 20 },
            d,
        ]);
    });
});

describe("GridLayers.scaleGrids", () => {
    it("maps a registered image's grid into this image's pixels", () => {
        formSchemasByName.set(SCHEMA_NAME, { id: 3, name: SCHEMA_NAME } as never);
        formAnnotations.set(
            9,
            grid(9, 5, "inst-2", {
                fovea: { x: 0, y: 0 },
                disc_edge: { x: 100, y: 0 },
            }),
        );
        // inst-2 is registered to this image at twice the size.
        const registration = {
            getLinkedImgIds: () => new Set(["inst-2"]),
            getRegistrationItem: () => undefined,
            mapPosition: (from: string, to: string, p: { x: number; y: number }) =>
                from === to ? p : { ...p, x: p.x * 2, y: p.y * 2 },
        };
        const viewer = {
            image: {
                image_id: "inst-1",
                instance: { id: "inst-1", cf_keypoints: null },
            },
        };
        const grids = new GridLayers(viewer as never, registration as never);
        expect(grids.scaleGrids()).toMatchObject([
            { key: 9, fovea: { x: 0, y: 0 }, discEdge: { x: 200, y: 0 } },
        ]);
    });
});
