import { describe, expect, it } from "vitest";
import { tickAt } from "./sliceTicks";

// 101 slices over 500 px: slice n sits at 5n px. The handle is at slice 80 (400 px), away from the ticks.
const at = (y: number, slices: number[]) => tickAt(y, 500, slices, 101, 80);

describe("tickAt", () => {
    it("hits a tick within 3 px and misses just outside", () => {
        expect(at(203, [40])).toBe(40);
        expect(at(197, [40])).toBe(40);
        expect(at(203.5, [40])).toBeNull();
        expect(at(196.5, [40])).toBeNull();
    });

    it("picks the nearest of two ticks in the band", () => {
        expect(at(201, [40, 41])).toBe(40);
        expect(at(204, [40, 41])).toBe(41);
    });

    it("leaves a press on the handle to the handle, even over a tick", () => {
        expect(at(403, [81])).toBeNull();
    });
});
