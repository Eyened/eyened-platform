import { describe, it, expect } from "vitest";
import { getPointsetRegistrations } from "./pointsetRegistration";

describe("getPointsetRegistrations", () => {
    it("maps corresponding indices: pt[i] on A → pt[i] on B", () => {
        const imgA = "aaa-public";
        const imgB = "bbb-public";
        // Scale×2 + translate(5,7) — index-aligned correspondences
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

        const regs = getPointsetRegistrations({ [imgA]: src, [imgB]: dst });
        expect(regs).toHaveLength(1);

        // Keys are sorted: aaa → bbb
        const { M, source, target } = regs[0]!;
        expect(source).toBe(imgA);
        expect(target).toBe(imgB);

        for (let i = 0; i < 3; i++) {
            const mapped = M.apply(src[i]!);
            expect(mapped.x).toBeCloseTo(dst[i]!.x);
            expect(mapped.y).toBeCloseTo(dst[i]!.y);
        }
    });

    it("skips null holes but still pairs by index", () => {
        const regs = getPointsetRegistrations({
            a: [{ x: 0, y: 0 }, null, { x: 0, y: 10 }, { x: 10, y: 0 }],
            b: [{ x: 1, y: 1 }, null, { x: 1, y: 21 }, { x: 21, y: 1 }],
        });
        expect(regs).toHaveLength(1);
        const M = regs[0]!.M;
        expect(M.apply({ x: 0, y: 0 }).x).toBeCloseTo(1);
        expect(M.apply({ x: 0, y: 10 }).y).toBeCloseTo(21);
    });

    it("returns no registration with fewer than 3 correspondences", () => {
        expect(
            getPointsetRegistrations({
                a: [{ x: 0, y: 0 }, { x: 1, y: 0 }],
                b: [{ x: 0, y: 0 }, { x: 2, y: 0 }],
            }),
        ).toHaveLength(0);
    });
});
