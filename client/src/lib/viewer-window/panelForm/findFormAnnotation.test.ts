import { describe, it, expect } from "vitest";
import { findFormAnnotation } from "./findFormAnnotation";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const base = {
    form_schema_id: 10,
    patient_id: 100,
    creator: { id: 5, name: "grader" },
    form_data: {},
} as FormAnnotationGET;

const ctx = {
    patientId: 100,
    studyId: 50,
    imageId: "img-200",
    laterality: "R" as const,
};

describe("findFormAnnotation", () => {
    it("in subtask context matches schema+creator+subtask only (ignores image)", () => {
        const annotations = [
            {
                ...base,
                id: 2,
                sub_task_id: 7,
                image_id: "other",
            },
            {
                ...base,
                id: 1,
                sub_task_id: 7,
                image_id: "img-200",
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            subTaskId: 7,
            schemaEntityType: "ImageInstance",
        });

        expect(result?.id).toBe(1); // lowest id
    });

    it("in subtask context does not create-match wrong subtask", () => {
        const annotations = [
            { ...base, id: 1, sub_task_id: 99, image_id: "img-200" },
        ] as FormAnnotationGET[];

        expect(
            findFormAnnotation({
                annotations,
                schemaId: 10,
                userId: 5,
                ctx,
                subTaskId: 7,
                schemaEntityType: "ImageInstance",
            }),
        ).toBeUndefined();
    });

    it("without subtask uses schema entity scope", () => {
        const annotations = [
            { ...base, id: 3, image_id: "img-200" },
            { ...base, id: 4, image_id: "other" },
        ] as FormAnnotationGET[];

        expect(
            findFormAnnotation({
                annotations,
                schemaId: 10,
                userId: 5,
                ctx,
                schemaEntityType: "ImageInstance",
            })?.id,
        ).toBe(3);
    });
});
