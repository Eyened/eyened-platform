import { describe, expect, it } from "vitest";
import { parseHexColour } from "./affineBlendRenderer";

describe("parseHexColour", () => {
    it("parses a hex colour into 0–1 channels", () => {
        expect(parseHexColour("#ff0000")).toEqual([1, 0, 0]);
        expect(parseHexColour("00ffff")).toEqual([0, 1, 1]);
        expect(parseHexColour("nope")).toEqual([0, 0, 0]);
    });
});
