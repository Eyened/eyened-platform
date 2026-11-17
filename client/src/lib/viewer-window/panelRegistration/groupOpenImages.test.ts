import { describe, expect, it } from "vitest";
import { annotationMatchesEye } from "./groupOpenImages";

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
