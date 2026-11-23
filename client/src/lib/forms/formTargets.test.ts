import { describe, expect, it } from "vitest";
import type { ImageMeta } from "$lib/workspace/imageMeta";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../types/openapi_types";
import {
    completion,
    incompleteForms,
    matchForms,
    targetsFor,
    type OpenImage,
} from "./formTargets";

const ME = 5;
const SET = 77;

function image(
    imageId: string,
    over: {
        instance?: string;
        patient?: number;
        identifier?: string;
        study?: number;
        date?: string;
        laterality?: "L" | "R";
        modality?: string;
    } = {},
): OpenImage {
    return {
        imageId,
        instance: {
            id: over.instance ?? imageId,
            patient: {
                id: over.patient ?? 1,
                identifier: over.identifier ?? "P-0001",
            },
            study: { id: over.study ?? 10, date: over.date ?? "2024-05-02" },
            laterality: over.laterality ?? "R",
            modality: over.modality ?? "OCT",
            etdrs_field: null,
            device: { manufacturer: "Heidelberg", model: "Spectralis" },
        } as unknown as ImageMeta,
    };
}

function schema(
    id: number,
    name: string,
    entity_type: FormSchemaGET["entity_type"] = "ImageInstance",
    body: unknown = {
        type: "object",
        required: ["quality"],
        properties: { quality: { type: "string", enum: ["good", "bad"] } },
    },
): FormSchemaGET {
    return { id, name, entity_type, schema: body } as FormSchemaGET;
}

let nextId = 9000;
function form(
    over: Omit<Partial<FormAnnotationGET>, "creator"> & { creator?: number },
) {
    const { creator, ...rest } = over;
    return {
        id: nextId++,
        form_schema_id: 1,
        patient_id: 1,
        study_id: 10,
        image_id: "img-a",
        laterality: "R",
        sub_task_id: SET,
        form_data: { quality: "good" },
        creator: { id: creator ?? ME, name: creator ? "J. de Vries" : "Me" },
        date_inserted: "2026-05-02T10:00:00",
        ...rest,
    } as FormAnnotationGET;
}

const QUALITY = schema(1, "Image quality grading");
const VISIT = schema(2, "Visit notes", "Study");
const REGISTRATION = schema(3, "Pointset registration");
const schemas = new Map([QUALITY, VISIT, REGISTRATION].map((s) => [s.id, s]));

describe("targetsFor", () => {
    it.each([
        ["ImageInstance", "OD · OCT · 2024-05-02", "OD · OCT · 2024-05-02"],
        ["StudyEye", "OD · 2024-05-02", "OD · 2024-05-02 (eye at visit)"],
        ["Study", "2024-05-02", "2024-05-02 (visit)"],
        ["Eye", "OD", "OD (eye)"],
        ["Patient", "Patient", "Patient"],
    ] as const)("names a %s target", (scope, name, group) => {
        const [target] = targetsFor([image("img-a")], scope);
        expect(target.name).toBe(name);
        expect(target.group).toBe(group);
    });

    it("an OCT volume and its projection are one target with both strip ids", () => {
        const targets = targetsFor(
            [
                image("oct-1", { instance: "oct-1" }),
                image("oct-1_proj", { instance: "oct-1" }),
            ],
            "ImageInstance",
        );
        expect(targets).toHaveLength(1);
        expect(targets[0].imageIds).toEqual(["oct-1", "oct-1_proj"]);
    });
});

describe("matchForms", () => {
    const base = {
        schemas,
        taskSchemaId: 1,
        userId: ME,
        subTaskId: SET,
    };

    it("a task row takes only my form in this set for its own image", () => {
        const other = form({ image_id: "img-b" });
        const otherSet = form({ sub_task_id: 78 });
        const { taskRows } = matchForms({
            ...base,
            forms: [other, otherSet],
            images: [image("img-a"), image("img-b", { laterality: "L" })],
        });
        expect(taskRows?.map((r) => r.form?.id ?? null)).toEqual([
            null,
            other.id,
        ]);
    });

    it("my newest task form fills the row; the older one and others' forms go to Other forms, newest first", () => {
        const older = form({ date_inserted: "2026-05-01T10:00:00" });
        const newer = form({ date_inserted: "2026-05-03T10:00:00" });
        const theirs = form({
            creator: 8,
            date_inserted: "2026-05-02T10:00:00",
        });
        const { taskRows, other } = matchForms({
            ...base,
            forms: [older, theirs, newer],
            images: [image("img-a")],
        });
        expect(taskRows?.[0].form?.id).toBe(newer.id);
        expect(other).toHaveLength(1);
        expect(other[0].forms.map((f) => f.id)).toEqual([theirs.id, older.id]);
    });

    it("an image form and a visit form make two groups, the image's first", () => {
        const visit = form({ form_schema_id: 2, image_id: null });
        const img = form({ creator: 8 });
        const { other } = matchForms({
            ...base,
            forms: [visit, img],
            images: [image("img-a")],
        });
        expect(other.map((g) => g.target.group)).toEqual([
            "OD · OCT · 2024-05-02",
            "2024-05-02 (visit)",
        ]);
    });

    it("leaves out registration forms and forms of images that aren't open", () => {
        const { other } = matchForms({
            ...base,
            forms: [
                form({ form_schema_id: 3, creator: 8 }),
                form({ creator: 8, image_id: "img-z" }),
            ],
            images: [image("img-a")],
        });
        expect(other).toEqual([]);
    });

    it("a patient form shows once, under its own patient", () => {
        const patientSchema = schema(4, "History", "Patient");
        const { other } = matchForms({
            ...base,
            schemas: new Map([...schemas, [4, patientSchema]]),
            forms: [form({ form_schema_id: 4, patient_id: 2, image_id: null })],
            images: [
                image("img-a"),
                image("img-b", { patient: 2, identifier: "P-0002" }),
                image("img-c", { patient: 2, identifier: "P-0002" }),
            ],
        });
        expect(other).toHaveLength(1);
        expect(other[0].target.patient).toBe("P-0002");
    });
});

describe("completion", () => {
    it("a required answer left out is not complete", () => {
        expect(completion(form({ form_data: {} }), QUALITY)).toBe("incomplete");
    });

    it("a required answer behind a $ref counts too", () => {
        const withRef = schema(5, "Lesions", "ImageInstance", {
            type: "object",
            $defs: {
                answers: {
                    type: "object",
                    required: ["count"],
                    properties: { count: { type: "integer" } },
                },
            },
            properties: { answers: { $ref: "#/$defs/answers" } },
        });
        expect(completion(form({ form_data: { answers: {} } }), withRef)).toBe(
            "incomplete",
        );
    });

    it("every answer valid is complete", () => {
        expect(completion(form({}), QUALITY)).toBe("complete");
    });
});

describe("incompleteForms", () => {
    it("counts a Grade row and my other form in this set that isn't complete", () => {
        const mine = form({ form_schema_id: 2, image_id: null, form_data: {} });
        const visitRequired = schema(2, "Visit notes", "Study", {
            type: "object",
            required: ["note"],
            properties: { note: { type: "string" } },
        });
        const all = new Map([...schemas, [2, visitRequired]]);
        const matched = matchForms({
            forms: [mine],
            images: [image("img-a")],
            schemas: all,
            taskSchemaId: 1,
            userId: ME,
            subTaskId: SET,
        });
        expect(incompleteForms(matched, all, ME, SET)).toEqual([
            "Image quality grading for OD · OCT · 2024-05-02: not graded",
            "Visit notes for 2024-05-02: not complete",
        ]);
    });
});
