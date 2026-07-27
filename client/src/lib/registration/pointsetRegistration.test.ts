import { describe, it, expect } from "vitest";
import {
    getPointsetRegistrations,
    toEnfaceRegistrationPoints,
} from "./pointsetRegistration";

describe("toEnfaceRegistrationPoints", () => {
    it("keeps plain 2D PublicID nodes", () => {
        const pts = [{ x: 1, y: 2 }];
        expect(toEnfaceRegistrationPoints("cf", pts)).toEqual({
            nodeId: "cf",
            points: pts,
        });
    });

    it("maps enface proj landmarks (index:null) onto *_proj; y is index-space", () => {
        const pts = [
            { x: 10, y: 3.5, index: null },
            { x: 20, y: 7.5, index: null },
        ];
        expect(toEnfaceRegistrationPoints("oct", pts)).toEqual({
            nodeId: "oct_proj",
            points: [
                { x: 10, y: 3.5 },
                { x: 20, y: 7.5 },
            ],
        });
    });

    it("maps OCT volume landmarks via (x, index+0.5) onto *_proj", () => {
        const pts = [
            { x: 10, y: 100, index: 3 },
            { x: 20, y: 200, index: 7 },
        ];
        expect(toEnfaceRegistrationPoints("oct", pts)).toEqual({
            nodeId: "oct_proj",
            points: [
                { x: 10, y: 3.5 },
                { x: 20, y: 7.5 },
            ],
        });
    });
});

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

    it("registers CF ↔ enface_proj on the *_proj node (not volume id)", () => {
        const cf = "cf-id";
        const oct = "oct-id";
        const cfPts = [
            { x: 0, y: 0 },
            { x: 10, y: 0 },
            { x: 0, y: 10 },
        ];
        // Enface proj storage: y is B-scan index space; index: null
        const projPts = [
            { x: 1, y: 2, index: null },
            { x: 11, y: 2, index: null },
            { x: 1, y: 12, index: null },
        ];

        const regs = getPointsetRegistrations({
            [cf]: cfPts,
            [oct]: projPts,
        });
        expect(regs).toHaveLength(1);
        expect(regs[0]!.source).toBe(cf);
        expect(regs[0]!.target).toBe(`${oct}_proj`);

        for (let i = 0; i < 3; i++) {
            const mapped = regs[0]!.M.apply(cfPts[i]!);
            expect(mapped.x).toBeCloseTo(projPts[i]!.x);
            expect(mapped.y).toBeCloseTo(projPts[i]!.y);
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
                a: [
                    { x: 0, y: 0 },
                    { x: 1, y: 0 },
                ],
                b: [
                    { x: 0, y: 0 },
                    { x: 2, y: 0 },
                ],
            }),
        ).toHaveLength(0);
    });
});
