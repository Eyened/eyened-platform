import { describe, expect, it } from "vitest";
import { seriesBlendWeights } from "./seriesBlendWeights";

describe("seriesBlendWeights", () => {
    it("starts on the first image and ends on the last", () => {
        expect(seriesBlendWeights(0, 3)).toEqual([1, 0, 0]);
        expect(seriesBlendWeights(1, 3)).toEqual([0, 0, 1]);
    });

    it("holds the middle image at the halfway point of three", () => {
        expect(seriesBlendWeights(0.5, 3)).toEqual([0, 1, 0]);
    });

    it("splits the weight between one consecutive pair", () => {
        expect(seriesBlendWeights(0.25, 3)).toEqual([0.5, 0.5, 0]);
        expect(seriesBlendWeights(0.75, 3)).toEqual([0, 0.5, 0.5]);
        expect(seriesBlendWeights(0.5, 2)).toEqual([0.5, 0.5]);
    });

    it("keeps a single image fully on", () => {
        expect(seriesBlendWeights(0.4, 1)).toEqual([1]);
        expect(seriesBlendWeights(0, 0)).toEqual([]);
    });
});
