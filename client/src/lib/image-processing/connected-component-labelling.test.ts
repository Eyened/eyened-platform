import { describe, expect, it } from "vitest";
import { BlobExtraction } from "./connected-component-labelling";

describe("BlobExtraction", () => {
    it("does not store foreground labels as background when there are more than 255 components", () => {
        // Isolated pixels with a gap so 8-connectivity does not merge them.
        const n = 256;
        const w = n * 2;
        const h = 1;
        const data = new Uint8Array(w * h);
        for (let i = 0; i < n; i++) {
            data[i * 2] = 1;
        }

        const labels = BlobExtraction(data, w, h);

        for (let i = 0; i < n; i++) {
            expect(labels[i * 2], `component ${i + 1}`).not.toBe(0);
        }
    });
});
