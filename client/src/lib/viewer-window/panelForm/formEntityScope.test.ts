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

    it("rejects a different patient", () => {
        const a = { ...annotation, patient_id: 999 } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "Patient", ctx)).toBe(false);
    });

    it("matches Patient, Study, and Eye", () => {
        const a = {
            ...annotation,
            study_id: 50,
            laterality: "R",
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "Patient", ctx)).toBe(true);
        expect(matchesFormEntityScope(a, "Study", ctx)).toBe(true);
        expect(matchesFormEntityScope(a, "Eye", ctx)).toBe(true);
    });

    it("rejects an unknown scope", () => {
        expect(matchesFormEntityScope(annotation, "Nope" as never, ctx)).toBe(
            false,
        );
    });

    it("treats null and undefined laterality as the same Eye scope", () => {
        const nullLateralityCtx = {
            patientId: 100,
            laterality: undefined,
        };
        const a = {
            ...annotation,
            laterality: null,
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "Eye", nullLateralityCtx)).toBe(true);
    });

    it("treats null and undefined study_id and laterality as the same StudyEye scope", () => {
        const nullStudyEyeCtx = {
            patientId: 100,
            studyId: undefined,
            laterality: undefined,
        };
        const a = {
            ...annotation,
            study_id: null,
            laterality: null,
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "StudyEye", nullStudyEyeCtx)).toBe(
            true,
        );
    });

    it("does not match Eye when laterality is R and ctx laterality is undefined", () => {
        const undefinedLateralityCtx = {
            patientId: 100,
            laterality: undefined,
        };
        const a = {
            ...annotation,
            laterality: "R",
        } as FormAnnotationGET;
        expect(matchesFormEntityScope(a, "Eye", undefinedLateralityCtx)).toBe(
            false,
        );
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

    it("builds payloads for Patient, Study, Eye, and ImageInstance", () => {
        const ctx = {
            patientId: 100,
            studyId: 50,
            imageId: "abc123",
            laterality: "R" as const,
        };
        expect(
            buildFormAnnotationCreatePayload({
                formSchemaId: 10,
                scope: "Patient",
                ctx,
            }),
        ).toEqual({
            form_schema_id: 10,
            patient_id: 100,
            sub_task_id: undefined,
            form_data: {},
        });
        expect(
            buildFormAnnotationCreatePayload({
                formSchemaId: 10,
                scope: "Study",
                ctx,
            }).study_id,
        ).toBe(50);
        expect(
            buildFormAnnotationCreatePayload({
                formSchemaId: 10,
                scope: "Eye",
                ctx,
            }).laterality,
        ).toBe("R");
        expect(
            buildFormAnnotationCreatePayload({
                formSchemaId: 10,
                scope: "ImageInstance",
                ctx,
            }),
        ).toMatchObject({
            study_id: 50,
            image_id: "abc123",
            laterality: "R",
        });
    });

    it("falls back to the patient payload for an unknown scope", () => {
        expect(
            buildFormAnnotationCreatePayload({
                formSchemaId: 10,
                scope: "Nope" as never,
                ctx: {
                    patientId: 100,
                    studyId: 50,
                    imageId: "abc123",
                    laterality: "R",
                },
            }),
        ).toEqual({
            form_schema_id: 10,
            patient_id: 100,
            sub_task_id: undefined,
            form_data: {},
        });
    });
});
