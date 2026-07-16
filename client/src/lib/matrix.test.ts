import { describe, it, expect } from "vitest";
import { Matrix, getMatrixFromPointSets } from "./matrix";

describe("Matrix", () => {
    it("identity maps a point to itself", () => {
        const p = Matrix.identity.apply({ x: 3, y: 5 });
        expect(p.x).toBeCloseTo(3);
        expect(p.y).toBeCloseTo(5);
    });

    it("from_translate_scale scales then translates", () => {
        const m = Matrix.from_translate_scale(10, 20, 2, 3);
        const p = m.apply({ x: 1, y: 1 });
        expect(p.x).toBeCloseTo(12); // 2*1 + 10
        expect(p.y).toBeCloseTo(23); // 3*1 + 20
    });

    it("inverse composed with the matrix yields the original point", () => {
        const m = Matrix.from_translate_scale(10, 20, 2, 3);
        const back = m.applyInverse({ x: 12, y: 23 });
        expect(back.x).toBeCloseTo(1);
        expect(back.y).toBeCloseTo(1);
    });

    it("throws when inverting a singular matrix", () => {
        const singular = new Matrix(0, 0, 0, 0, 0, 0, 0, 0, 0);
        expect(() => singular.inverse).toThrow("not invertible");
    });

    it("fromRows rejects a non-3x3 input", () => {
        expect(() =>
            Matrix.fromRows([
                [1, 2],
                [3, 4],
            ]),
        ).toThrow("3x3");
    });
});

describe("getMatrixFromPointSets", () => {
    it("recovers a known affine transform from point correspondences", () => {
        const src = [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 0, y: 1 },
        ];
        const truth = Matrix.from_translate_scale(5, 7, 2, 2); // scale 2 + translate (5,7)
        const dst = src.map((p) => truth.apply(p));

        const m = getMatrixFromPointSets(src, dst);
        expect(m).toBeDefined();

        const got = m!.apply({ x: 2, y: 3 });
        const expected = truth.apply({ x: 2, y: 3 });
        expect(got.x).toBeCloseTo(expected.x);
        expect(got.y).toBeCloseTo(expected.y);
    });
});
