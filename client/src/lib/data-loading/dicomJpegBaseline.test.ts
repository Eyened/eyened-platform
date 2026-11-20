import { afterEach, describe, expect, it, vi } from "vitest";
import { decodeJpegBaselineFrame } from "./dicomJpegBaseline";

class FakeBitmap {
    width = 2;
    height = 1;
    close = vi.fn();
}

function stubCanvas(data: number[] | null) {
    vi.stubGlobal(
        "createImageBitmap",
        vi.fn(async () => new FakeBitmap()),
    );
    vi.stubGlobal(
        "OffscreenCanvas",
        class {
            constructor(
                public width: number,
                public height: number,
            ) {}
            getContext() {
                if (!data) return null;
                return {
                    drawImage() {},
                    getImageData: () => ({
                        data: Uint8ClampedArray.from(data),
                        width: 2,
                        height: 1,
                    }),
                };
            }
        },
    );
}

describe("decodeJpegBaselineFrame", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("packs mono pixels from the red channel", async () => {
        stubCanvas([10, 0, 0, 255, 40, 0, 0, 255]);
        const out = await decodeJpegBaselineFrame(new Uint8Array([1]), 1);
        expect(Array.from(out)).toEqual([10, 40]);
    });

    it("packs RGB pixels", async () => {
        stubCanvas([1, 2, 3, 255, 4, 5, 6, 255]);
        const out = await decodeJpegBaselineFrame(new Uint8Array([1]), 3);
        expect(Array.from(out)).toEqual([1, 2, 3, 4, 5, 6]);
    });

    it("throws when the 2d context is missing", async () => {
        stubCanvas(null);
        await expect(
            decodeJpegBaselineFrame(new Uint8Array([1]), 1),
        ).rejects.toThrow(/2d context/);
    });
});
