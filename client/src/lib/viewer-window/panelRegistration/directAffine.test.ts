import { Matrix } from "$lib/matrix";
import { AffineRegistration } from "$lib/registration/affine";
import { ParabolicRegistration } from "$lib/registration/parabolic";
import { describe, expect, it } from "vitest";
import { directAffineMatrix, firstBlendOverlay } from "./directAffine";

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

describe("firstBlendOverlay", () => {
    it("picks the first checked image in top-row order", () => {
        expect(firstBlendOverlay(["a", "b", "c"], "b", ["c", "a"])).toBe("a");
        expect(firstBlendOverlay(["a", "b"], "a", [])).toBeUndefined();
    });
});
