import { Matrix } from "$lib/matrix";
import { AffineRegistration } from "$lib/registration/affine";
import { ParabolicRegistration } from "$lib/registration/parabolic";
import { describe, expect, it } from "vitest";
import { affineFromFormData, directAffineMatrix } from "./directAffine";

describe("directAffineMatrix", () => {
    it("returns the affine matrix and ignores other edge types", () => {
        const M = new Matrix(2, 0, 1, 0, 3, 4);
        expect(directAffineMatrix(new AffineRegistration("a", "b", M))).toBe(M);
        expect(
            directAffineMatrix(
                new ParabolicRegistration(
                    "a",
                    "b",
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0],
                ),
            ),
        ).toBeNull();
        expect(directAffineMatrix(undefined)).toBeNull();
    });
});

describe("affineFromFormData", () => {
    const src = [
        { x: 0, y: 0 },
        { x: 10, y: 0 },
        { x: 0, y: 10 },
    ];
    const dst = [
        { x: 5, y: 7 },
        { x: 25, y: 7 },
        { x: 5, y: 27 },
    ];

    it("returns the affine for the open annotation pair", () => {
        const M = affineFromFormData(
            { fixed: src, moving: dst },
            "fixed",
            "moving",
        );
        expect(M).not.toBeNull();
        expect(M!.apply({ x: 0, y: 0 }).x).toBeCloseTo(5);
        expect(M!.apply({ x: 0, y: 0 }).y).toBeCloseTo(7);
    });

    it("inverts when form_data stores the pair in the other direction", () => {
        const M = affineFromFormData(
            { moving: dst, fixed: src },
            "moving",
            "fixed",
        );
        expect(M).not.toBeNull();
        expect(M!.apply({ x: 5, y: 7 }).x).toBeCloseTo(0);
        expect(M!.apply({ x: 5, y: 7 }).y).toBeCloseTo(0);
    });

    it("returns null when the annotation has no affine yet", () => {
        expect(affineFromFormData({}, "fixed", "moving")).toBeNull();
        expect(affineFromFormData(null, "fixed", "moving")).toBeNull();
        expect(
            affineFromFormData(
                {
                    fixed: [
                        { x: 0, y: 0 },
                        { x: 1, y: 0 },
                    ],
                    moving: [
                        { x: 2, y: 0 },
                        { x: 3, y: 0 },
                    ],
                },
                "fixed",
                "moving",
            ),
        ).toBeNull();
    });
});
