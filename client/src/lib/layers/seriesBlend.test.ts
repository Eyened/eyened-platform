import { describe, expect, it } from "vitest";
import { defaultTicks, nextStop, seriesLayerWeights } from "./seriesBlend";

describe("defaultTicks", () => {
    const items = [
        { id: "a", date: "2020-01-01", modality: "CF" },
        { id: "b", date: "2020-03-02", modality: "CF" },
        { id: "this", date: "2020-05-01", modality: "CF" },
        { id: "faf", date: "2020-05-02", modality: "FAF" },
        { id: "e", date: "2020-06-30", modality: "CF" },
    ];

    it("ticks this image and its modality's nearest by date up to the cap, the earlier winning a tie", () => {
        // b and e are both 60 days away.
        expect(defaultTicks(items, "this", 2)).toEqual(["this", "b"]);
        expect(defaultTicks(items, "this", 3)).toEqual(["this", "b", "e"]);
        expect(defaultTicks(items, "this", 16)).toEqual([
            "this",
            "b",
            "e",
            "a",
        ]);
    });
});

describe("seriesLayerWeights", () => {
    it("computes weights in date order and returns them with this image first", () => {
        // Halfway between this (index 1) and e (index 2).
        expect(seriesLayerWeights(["a", "this", "e"], "this", 1.5)).toEqual([
            0.5, 0, 0.5,
        ]);
    });
});

describe("nextStop", () => {
    it("goes to the next whole image and stops at the ends", () => {
        expect(nextStop(1.4, 1, 4)).toBe(2);
        expect(nextStop(1.4, -1, 4)).toBe(1);
        expect(nextStop(2, -1, 4)).toBe(1);
        expect(nextStop(3, 1, 4)).toBe(3);
        expect(nextStop(0, -1, 4)).toBe(0);
    });
});
