import { describe, expect, it } from "vitest";
import { classPixelCounts } from "./classArea";

describe("classPixelCounts", () => {
    it("MultiClass counts pixels equal to the class index; MultiLabel counts pixels with the class bit set", () => {
        const classes = Uint8Array.from([0, 1, 1, 2, 3, 7]);
        expect([...classPixelCounts(classes, false, [1, 2, 3])]).toEqual([
            [1, 2],
            [2, 1],
            [3, 1],
        ]);
        // Bits: class 1 = 1, class 2 = 2, class 3 = 4.
        const labels = Uint8Array.from([0, 1, 3, 2, 4, 7]);
        expect([...classPixelCounts(labels, true, [1, 2, 3])]).toEqual([
            [1, 3],
            [2, 3],
            [3, 2],
        ]);
    });
});
