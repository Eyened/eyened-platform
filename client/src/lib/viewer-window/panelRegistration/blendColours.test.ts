import { describe, expect, it } from "vitest";
import { blendColours } from "./blendColours";

const red: [number, number, number] = [1, 0, 0];
const green: [number, number, number] = [0, 1, 0];
const blue: [number, number, number] = [0, 0, 1];
const cyan: [number, number, number] = [0, 1, 1];
const magenta: [number, number, number] = [1, 0, 1];
const yellow: [number, number, number] = [1, 1, 0];

describe("blendColours", () => {
    it("leaves a single image untinted", () => {
        expect(blendColours(1)).toEqual({ untinted: true, colours: [[1, 1, 1]] });
    });

    it("uses red and cyan for two images", () => {
        expect(blendColours(2).colours).toEqual([red, cyan]);
        expect(blendColours(2).untinted).toBe(false);
    });

    it("uses red, green, and blue for three images", () => {
        expect(blendColours(3).colours).toEqual([red, green, blue]);
    });

    it("continues cyan, magenta, yellow and then repeats", () => {
        expect(blendColours(4).colours).toEqual([red, green, blue, cyan]);
        expect(blendColours(6).colours).toEqual([red, green, blue, cyan, magenta, yellow]);
        expect(blendColours(7).colours[6]).toEqual(red);
    });

    it("returns no colours for an empty set", () => {
        expect(blendColours(0)).toEqual({ untinted: false, colours: [] });
    });
});
