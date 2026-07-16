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

describe("findFormAnnotation", () => {
    it("returns matching annotation for current user, schema, and image", () => {
        const annotations = [
            {
                ...baseAnnotation,
                id: 1,
                image_id: 200,
                creator: { id: 5, name: "grader" },
            },
            {
                ...baseAnnotation,
                id: 2,
                image_id: 200,
                creator: { id: 99, name: "other" },
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            patientId: 100,
            imageId: 200,
            formImageScope: true,
            entityType: "ImageInstance",
        });

        expect(result?.id).toBe(1);
    });

    it("returns undefined when no annotation matches", () => {
        const result = findFormAnnotation({
            annotations: [baseAnnotation],
            schemaId: 10,
            userId: 5,
            patientId: 100,
            imageId: 999,
            formImageScope: true,
            entityType: "ImageInstance",
        });

        expect(result).toBeUndefined();
    });

    it("matches StudyEye by study and laterality when formImageScope is false", () => {
        const annotations = [
            {
                ...baseAnnotation,
                id: 3,
                study_id: 50,
                laterality: "R",
                image_id: undefined,
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            patientId: 100,
            studyId: 50,
            laterality: "R",
            formImageScope: false,
            entityType: "StudyEye",
        });

        expect(result?.id).toBe(3);
    });

    it("returns highest id when multiple match (defensive)", () => {
        const annotations = [
            { ...baseAnnotation, id: 1, image_id: 200 },
            { ...baseAnnotation, id: 2, image_id: 200 },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            patientId: 100,
            imageId: 200,
            formImageScope: true,
            entityType: "ImageInstance",
        });

        expect(result?.id).toBe(2);
    });
});
