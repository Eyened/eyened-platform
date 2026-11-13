import { describe, expect, it } from "vitest";
import { buildImageDataUrl } from "./imageDataUrl";

describe("buildImageDataUrl", () => {
    it("returns bare data URL without query", () => {
        expect(buildImageDataUrl("abc")).toBe("/api/images/abc/data");
    });

    it("appends storage_id", () => {
        expect(buildImageDataUrl("abc", { storage_id: 42 })).toBe(
            "/api/images/abc/data?storage_id=42",
        );
    });

    it("omits undefined query values", () => {
        expect(
            buildImageDataUrl("abc", { meta: true, storage_id: undefined }),
        ).toBe("/api/images/abc/data?meta=true");
    });
});
