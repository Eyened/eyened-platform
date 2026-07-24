import { describe, it, expect } from "vitest";
import {
    buildFormAnnotationCreatePayload,
    matchesFormEntityScope,
    resolveFormEntityScope,
} from "./formEntityScope";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const annotation = {
    id: 1,
    patient_id: 100,
    form_schema_id: 10,
    creator: { id: 5, name: "grader" },
    form_data: {},
} as FormAnnotationGET;

describe("resolveFormEntityScope", () => {
    it("uses schema entity type", () => {
        expect(resolveFormEntityScope("StudyEye")).toBe("StudyEye");
    });

    it("falls back to ImageInstance when schema type missing", () => {
        expect(resolveFormEntityScope(undefined)).toBe("ImageInstance");
        expect(resolveFormEntityScope(null)).toBe("ImageInstance");
    });
});

describe("matchesFormEntityScope", () => {
    const ctx = {
        patientId: 100,
        studyId: 50,
        imageId: "abc123",
        laterality: "R" as const,
    };

    it("matches StudyEye by study and laterality", () => {
        const a = {
            ...annotation,
            study_id: 50,
            laterality: "R",
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "StudyEye", ctx)).toBe(true);
    });

    it("does not match StudyEye when laterality differs", () => {
        const a = {
            ...annotation,
            study_id: 50,
            laterality: "L",
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "StudyEye", ctx)).toBe(false);
    });

    it("matches ImageInstance by image id", () => {
        const a = { ...annotation, image_id: "abc123" } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "ImageInstance", ctx)).toBe(true);
    });
});

describe("buildFormAnnotationCreatePayload", () => {
    it("omits image_id for StudyEye scope", () => {
        const payload = buildFormAnnotationCreatePayload({
            formSchemaId: 10,
            scope: "StudyEye",
            ctx: {
                patientId: 100,
                studyId: 50,
                imageId: "abc123",
                laterality: "R",
            },
            subTaskId: 7,
        });

        expect(payload).toEqual({
            form_schema_id: 10,
            patient_id: 100,
            study_id: 50,
            laterality: "R",
            sub_task_id: 7,
            form_data: {},
        });
        expect("image_id" in payload).toBe(false);
    });
});
