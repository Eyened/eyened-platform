import { describe, it, expect } from "vitest";
import {
    serializeViewersParam,
    instanceIdFromImageId,
    parseViewerToken,
} from "./viewerViewState";

describe("serializeViewersParam", () => {
    it("omits empty serialize", () => {
        expect(serializeViewersParam([])).toBe("");
    });

    it("does not percent-encode dots in typical ids", () => {
        const encoded = serializeViewersParam([
            { id: "q4m7gj6h", index: 119 },
            { id: "vc88pyyh", index: 15 },
        ]);
        expect(encoded).toBe("q4m7gj6h.119,vc88pyyh.15");
        expect(encoded.includes("%")).toBe(false);
        expect(encoded.includes(":")).toBe(false);
    });
});

describe("instanceIdFromImageId", () => {
    it("strips _proj suffix", () => {
        expect(instanceIdFromImageId("abc_proj")).toBe("abc");
        expect(instanceIdFromImageId("abc")).toBe("abc");
    });
});

describe("parseViewerToken", () => {
    it("reads id and id.index and rejects malformed tokens", () => {
        expect(
            ["aaa.42", "fff", "bad!", "bbb.x", "ccc.-1", "ddd.3.5", ""].map(
                parseViewerToken,
            ),
        ).toEqual([
            { id: "aaa", index: 42 },
            { id: "fff" },
            null,
            null,
            null,
            null,
            null,
        ]);
    });
});
