import { describe, expect, it } from "vitest";
import {
    barState,
    nonDefaultLabel,
    notchToStretch,
    readoutParts,
    stretchToNotch,
} from "./viewControlsFit";

describe("barState", () => {
    const bscan = { full: 620, compact: 380 };

    it("picks the largest state that fits, at each boundary", () => {
        expect(barState(bscan, 620)).toBe("full");
        expect(barState(bscan, 619)).toBe("compact");
        expect(barState(bscan, 380)).toBe("compact");
        expect(barState(bscan, 379)).toBe("folded");
    });

    it("never gives a type without stretch the full state", () => {
        expect(barState({ full: null, compact: 300 }, 5000)).toBe("compact");
    });
});

describe("stretch notches", () => {
    it("keep the slider on whole notches and clamp values past its ends", () => {
        expect(stretchToNotch(0.3)).toBe(0);
        expect(stretchToNotch(0.01)).toBe(0);
        expect(stretchToNotch(1000)).toBe(stretchToNotch(20));
        expect(notchToStretch(stretchToNotch(8))).toBeCloseTo(8, 0);
    });
});

describe("nonDefaultLabel", () => {
    const defaults = {
        mode: "Original" as const,
        windowLevel: { min: 30, max: 225 },
        defaultWindowLevel: { min: 30, max: 225 },
        stretch: 2.7,
        defaultStretch: 2.7,
    };

    it("names every setting that differs, in bar order", () => {
        expect(
            nonDefaultLabel({
                ...defaults,
                mode: "CLAHE",
                windowLevel: { min: 0, max: 200 },
                stretch: 4,
            }),
        ).toBe("CLAHE · W/L 0–200 · 4×");
    });

    it("ignores stretch on types without it", () => {
        expect(
            nonDefaultLabel({
                ...defaults,
                stretch: undefined,
                defaultStretch: 2.7,
            }),
        ).toBe("");
    });
});

describe("readoutParts", () => {
    const w = { numbers: 200, count: 60, word: 50, readout: 60 };

    it("drops the count and the word first, then the number line", () => {
        expect(readoutParts(w, 370)).toEqual({
            numbers: true,
            count: true,
            word: true,
        });
        expect(readoutParts(w, 369)).toEqual({
            numbers: true,
            count: false,
            word: false,
        });
        expect(readoutParts(w, 259)).toEqual({
            numbers: false,
            count: false,
            word: true,
        });
    });
});
