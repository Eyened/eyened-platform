import { describe, expect, it, vi } from "vitest";

vi.mock("jpeg-lossless-decoder-js", () => ({
    Decoder: class {
        decode(): Uint16Array {
            return new Uint16Array([300, 1]);
        }
    },
}));

describe("decodeJpegLosslessFrame", () => {
    it("truncates 16-bit samples to 8 bits", async () => {
        const { decodeJpegLosslessFrame } = await import("./dicomJpegLossless");
        const out = await decodeJpegLosslessFrame(new Uint8Array([1]), 16);
        expect(Array.from(out)).toEqual([44, 1]);
    });
});
