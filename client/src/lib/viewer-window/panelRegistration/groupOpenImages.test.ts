import { describe, expect, it } from "vitest";
import {
    annotationMatchesEye,
    canOpenRegistration,
    groupOpenImages,
    orderByInstanceIds,
    type OpenImage,
} from "./groupOpenImages";

const img = (
    patch: Partial<OpenImage> & Pick<OpenImage, "imageId">,
): OpenImage => ({
    instanceId: patch.imageId,
    patientId: 1,
    laterality: "R",
    studyId: 9,
    ...patch,
});

describe("orderByInstanceIds", () => {
    it("follows instance order and keeps images of one instance together", () => {
        const ordered = orderByInstanceIds(
            [
                img({ imageId: "late", instanceId: "inst-b" }),
                img({ imageId: "proj", instanceId: "inst-a" }),
                img({ imageId: "early", instanceId: "inst-b" }),
            ],
            ["inst-b", "inst-a"],
        );
        expect(ordered.map((image) => image.imageId)).toEqual([
            "late",
            "early",
            "proj",
        ]);
    });
});

describe("groupOpenImages", () => {
    it("splits by patient and eye and keeps top-row order inside a group", () => {
        const groups = groupOpenImages([
            img({ imageId: "a", laterality: "L" }),
            img({ imageId: "b", patientId: 2, laterality: "R" }),
            img({ imageId: "c", laterality: "L" }),
            img({ imageId: "d", laterality: null }),
        ]);
        expect(
            groups.map((g) => [
                g.patientId,
                g.laterality,
                g.images.map((i) => i.imageId),
            ]),
        ).toEqual([
            [1, "L", ["a", "c"]],
            [2, "R", ["b"]],
            [1, null, ["d"]],
        ]);
    });

    it("puts two images with no laterality in one unset group, not with a known eye", () => {
        const groups = groupOpenImages([
            img({ imageId: "a", laterality: null }),
            img({ imageId: "b", laterality: "R" }),
            img({ imageId: "c", laterality: null }),
        ]);
        const unset = groups.find((g) => g.laterality === null);
        expect(unset?.images.map((i) => i.imageId)).toEqual(["a", "c"]);
        expect(
            groups
                .find((g) => g.laterality === "R")
                ?.images.map((i) => i.imageId),
        ).toEqual(["b"]);
    });
});

describe("canOpenRegistration", () => {
    it("requires a fixed image, a different reference image, and a choice", () => {
        expect(canOpenRegistration("a", "b", "new")).toBe(true);
        expect(canOpenRegistration("a", "b", "21")).toBe(true);
        expect(canOpenRegistration("a", "", "new")).toBe(false);
        expect(canOpenRegistration("", "b", "new")).toBe(false);
        expect(canOpenRegistration("a", "a", "new")).toBe(false);
        expect(canOpenRegistration("a", "b", null)).toBe(false);
        expect(canOpenRegistration("a", "b", "")).toBe(false);
    });
});

describe("annotationMatchesEye", () => {
    const base = {
        form_schema_id: 4,
        patient_id: 1,
        laterality: "R" as const,
        image_id: null,
    };

    it("matches schema, patient, and eye", () => {
        expect(annotationMatchesEye(base, 4, 1, "R", () => undefined)).toBe(
            true,
        );
        expect(annotationMatchesEye(base, 4, 1, "L", () => undefined)).toBe(
            false,
        );
        expect(annotationMatchesEye(base, 9, 1, "R", () => undefined)).toBe(
            false,
        );
        expect(
            annotationMatchesEye(
                { ...base, patient_id: 2 },
                4,
                1,
                "R",
                () => undefined,
            ),
        ).toBe(false);
    });

    it("uses the image laterality when the annotation has none", () => {
        expect(
            annotationMatchesEye(
                { ...base, laterality: null, image_id: "img" },
                4,
                1,
                "L",
                () => "L",
            ),
        ).toBe(true);
    });

    it("keeps an unset annotation out of a known eye", () => {
        expect(
            annotationMatchesEye(
                { ...base, laterality: null, image_id: null },
                4,
                1,
                "R",
                () => undefined,
            ),
        ).toBe(false);
        expect(
            annotationMatchesEye(
                { ...base, laterality: null, image_id: null },
                4,
                1,
                null,
                () => undefined,
            ),
        ).toBe(true);
    });
});
