import { describe, expect, it } from "vitest";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { imageLines, pointBinding, registrationRows } from "./pointsets";

const pt = { x: 1, y: 2 };

/** A synthetic pointset registration of patient 1. */
function reg(
    id: number,
    form_data: Record<string, unknown>,
    over: Partial<FormAnnotationGET> = {},
): FormAnnotationGET {
    return {
        id,
        form_schema_id: 4,
        patient_id: 1,
        laterality: "R",
        image_id: "elsewhere",
        creator: { id: 5, name: "Grader 5" },
        form_data,
        ...over,
    } as unknown as FormAnnotationGET;
}

describe("registrationRows", () => {
    it("lists this eye's registrations with points here, created here or current, in id order", () => {
        const rows = registrationRows(
            [
                reg(14, { "inst-2": [pt] }, { id: 14 }), // current, no points here
                reg(12, { "inst-1": [pt] }),
                reg(11, {}, { image_id: "inst-1" }), // created here, empty
                reg(13, { "inst-1": [pt] }, { laterality: "L" }), // other eye
                reg(15, { "inst-1": [null] }), // only an empty slot here
                reg(16, { "inst-1": [pt] }, { form_schema_id: 9 }),
            ],
            {
                schemaId: 4,
                instanceId: "inst-1",
                patientId: 1,
                laterality: "R",
                currentId: 14,
                imageLaterality: () => undefined,
            },
        );
        expect(rows.map((r) => r.id)).toEqual([11, 12, 14]);
    });
});

describe("imageLines", () => {
    const loaded = [
        { id: "inst-1", name: "CF · 2022-05-10", device: "Topcon Maestro2" },
        { id: "inst-2", name: "FAF · 2024-03-12", device: "" },
    ];

    it("puts this image first, reads a gap as '2 · no 3' and names unloaded images by public ID", () => {
        const lines = imageLines(
            { gone: [pt], "inst-2": [pt, pt, null], "inst-1": [pt, pt, pt] },
            "inst-1",
            loaded,
        );
        expect(lines).toEqual([
            {
                name: "This CF · 2022-05-10",
                device: "Topcon Maestro2",
                points: "3 points",
                gap: false,
            },
            {
                name: "FAF · 2024-03-12",
                device: "",
                points: "2 · no 3",
                gap: true,
            },
            { name: "gone (not loaded)", device: "", points: "", gap: false },
        ]);
    });

    it("says this image has no points when it is not in the registration yet, and gives nothing for an empty registration", () => {
        expect(imageLines({ "inst-2": [pt] }, "inst-1", loaded)?.[0]).toEqual({
            name: "This CF · 2022-05-10",
            device: "Topcon Maestro2",
            points: "no points",
            gap: false,
        });
        expect(imageLines({ "inst-2": [null] }, "inst-1", loaded)).toBeNull();
    });
});

describe("pointBinding", () => {
    it("binds the eye's current registration on 2D images, editable only while P is armed and it is yours", () => {
        const current = reg(12, {});
        const yours = () => true;
        const base = {
            armed: true,
            hidden: false,
            is2D: true,
            current,
            canEdit: yours,
        };
        expect(pointBinding(base)).toEqual({ id: 12, canEdit: true });
        expect(pointBinding({ ...base, armed: false })).toEqual({
            id: 12,
            canEdit: false,
        });
        expect(pointBinding({ ...base, canEdit: () => false })).toEqual({
            id: 12,
            canEdit: false,
        });
        expect(pointBinding({ ...base, is2D: false })).toBeNull();
        expect(pointBinding({ ...base, hidden: true })).toBeNull();
        expect(pointBinding({ ...base, current: null })).toBeNull();
    });
});
