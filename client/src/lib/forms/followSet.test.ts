import { describe, expect, it } from "vitest";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../types/openapi_types";
import { followSet } from "./followSet";
import type { OpenImage } from "./formTargets";

const ME = 5;
const SET = 77;
const QUALITY = {
    id: 1,
    name: "Image quality grading",
    entity_type: "ImageInstance",
    schema: {},
} as unknown as FormSchemaGET;

function image(id: string): OpenImage {
    return {
        imageId: id,
        instance: {
            id,
            patient: { id: 1, identifier: "P-0001" },
            study: { id: 10, date: "2024-05-02" },
            laterality: "R",
            modality: "OCT",
            etdrs_field: null,
            device: { manufacturer: "Heidelberg", model: "Spectralis" },
        } as never,
    };
}

function form(id: number, over: Partial<FormAnnotationGET> = {}) {
    return {
        id,
        form_schema_id: 1,
        patient_id: 1,
        study_id: 10,
        image_id: "img-a",
        laterality: "R",
        sub_task_id: SET,
        form_data: {},
        creator: { id: ME, name: "Me" },
        date_inserted: "2026-05-02T10:00:00",
        ...over,
    } as FormAnnotationGET;
}

const base = {
    schema: QUALITY,
    images: [image("img-a"), image("img-b")],
    selectedImageId: "img-a",
    userId: ME,
    subTaskId: SET,
};

describe("followSet", () => {
    it("shows my form of the schema for the selected viewport's target", () => {
        const arrival = followSet({ ...base, forms: [form(1)] });
        expect(arrival.kind).toBe("form");
        if (arrival.kind === "form") {
            expect(arrival.form.id).toBe(1);
            expect(arrival.target.imageIds).toEqual(["img-a"]);
        }
    });

    it("offers Grade for the selected viewport's target when I have no form for it", () => {
        const arrival = followSet({ ...base, forms: [] });
        expect(arrival.kind).toBe("grade");
        if (arrival.kind === "grade")
            expect(arrival.target.imageIds).toEqual(["img-a"]);
    });

    it("has nothing to grade with no image in the selected viewport", () => {
        expect(
            followSet({ ...base, selectedImageId: null, forms: [form(1)] })
                .kind,
        ).toBe("nothing");
    });
});
