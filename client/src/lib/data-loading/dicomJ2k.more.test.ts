import { afterEach, describe, expect, it, vi } from "vitest";

const locateCalls: string[] = [];

vi.mock("@cornerstonejs/codec-openjpeg/decodewasmjs", () => ({
    default: vi.fn(async (opts: { locateFile: (file: string) => string }) => {
        locateCalls.push(opts.locateFile("notes.txt"));
        locateCalls.push(opts.locateFile("codec.wasm"));
        opts.print?.("ok");
        opts.printErr?.("err");
        return { J2KDecoder: class {} };
    }),
}));

vi.mock("@cornerstonejs/codec-openjpeg/decodewasm?url", () => ({
    default: "relative.wasm",
}));

describe("J2K codec edges", () => {
    afterEach(() => {
        locateCalls.length = 0;
    });

    it("resolves wasm paths and truncates 16-bit samples", async () => {
        const { createJ2kDecoder, decodeWithJ2kDecoder } = await import(
            "./dicomJ2kCodec"
        );
        await createJ2kDecoder();
        expect(locateCalls[0]).toBe("notes.txt");
        expect(locateCalls[1]).toBe("relative.wasm");

        const unsigned = new Uint8Array(new Uint16Array([300, 10]).buffer);
        const signed = new Uint8Array(new Int16Array([-2, 4]).buffer);
        const decoder = {
            getEncodedBuffer: (n: number) => new Uint8Array(n),
            decode: () => {},
            getFrameInfo: () => ({
                width: 1,
                height: 2,
                bitsPerSample: 16,
                componentCount: 1,
                isSigned: false,
            }),
            getDecodedBuffer: () => unsigned,
        };
        expect(
            Array.from(decodeWithJ2kDecoder(decoder, new Uint8Array([1]))),
        ).toEqual([44, 10]);
        decoder.getFrameInfo = () => ({
            width: 1,
            height: 2,
            bitsPerSample: 16,
            componentCount: 1,
            isSigned: true,
        });
        decoder.getDecodedBuffer = () => signed;
        expect(
            Array.from(decodeWithJ2kDecoder(decoder, new Uint8Array([1])))[0],
        ).toBe(254);
    });
});
