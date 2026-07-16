import { describe, it, expect } from "vitest";
import { findFormAnnotation } from "./findFormAnnotation";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const baseAnnotation = {
    id: 1,
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
    it("returns matching annotation for ImageInstance scope", () => {
        const annotations = [
            {
                ...baseAnnotation,
                id: 1,
                image_id: "img-200",
                creator: { id: 5, name: "grader" },
            },
            {
                ...baseAnnotation,
                id: 2,
                image_id: "img-200",
                creator: { id: 99, name: "other" },
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            taskConfig: { form_entity_scope: "ImageInstance" },
            schemaEntityType: "ImageInstance",
        });

        expect(result?.id).toBe(1);
    });

    it("returns undefined when no annotation matches", () => {
        const result = findFormAnnotation({
            annotations: [baseAnnotation],
            schemaId: 10,
            userId: 5,
            ctx: { ...ctx, imageId: "missing" },
            taskConfig: { form_entity_scope: "ImageInstance" },
            schemaEntityType: "ImageInstance",
        });

        expect(result).toBeUndefined();
    });

    it("matches StudyEye when form_entity_scope is StudyEye", () => {
        const annotations = [
            {
                ...baseAnnotation,
                id: 3,
                study_id: 50,
                laterality: "R",
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            taskConfig: { form_entity_scope: "StudyEye" },
            schemaEntityType: "StudyEye",
        });

        expect(result?.id).toBe(3);
    });

    it("supports legacy form_image_scope true", () => {
        const annotations = [
            { ...baseAnnotation, id: 1, image_id: "img-200" },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            taskConfig: { form_image_scope: true },
            schemaEntityType: "StudyEye",
        });

        expect(result?.id).toBe(1);
    });

    it("returns highest id when multiple match (defensive)", () => {
        const annotations = [
            { ...baseAnnotation, id: 1, image_id: "img-200" },
            { ...baseAnnotation, id: 2, image_id: "img-200" },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            taskConfig: { form_entity_scope: "ImageInstance" },
            schemaEntityType: "ImageInstance",
        });

        expect(result?.id).toBe(2);
    });
});
