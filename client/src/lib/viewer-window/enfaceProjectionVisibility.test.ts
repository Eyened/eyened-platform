import { describe, expect, it } from "vitest";
import { classWinners } from "./enfaceProjectionVisibility";

// Three en-face pixels; listed out of class order on purpose.
const classes = [
    { index: 2, values: Uint8Array.of(9, 0, 9) },
    { index: 1, values: Uint8Array.of(9, 9, 0) },
];

describe("classWinners", () => {
    it("gives each pixel the active class where present, else the lowest visible class, never a hidden one", () => {
        const both = new Set([1, 2]);
        expect([...classWinners(classes, 2, both)]).toEqual([2, 1, 2]);
        expect([...classWinners(classes, undefined, both)]).toEqual([1, 1, 2]);
        expect([...classWinners(classes, 1, new Set([2]))]).toEqual([2, 0, 2]);
    });
});
