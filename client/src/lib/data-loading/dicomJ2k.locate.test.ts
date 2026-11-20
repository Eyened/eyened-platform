import { describe, expect, it, vi } from "vitest";

vi.mock("@cornerstonejs/codec-openjpeg/decodewasmjs", () => ({
    default: vi.fn(async (opts: { locateFile: (file: string) => string }) => {
        opts.locateFile("codec.wasm");
        return { J2KDecoder: class {} };
    }),
}));

vi.mock("@cornerstonejs/codec-openjpeg/decodewasm?url", () => ({
    default: "https://cdn.example/codec.wasm",
}));

describe("J2K wasm URL", () => {
    it("keeps an absolute wasm URL", async () => {
        const factory = (
            await import("@cornerstonejs/codec-openjpeg/decodewasmjs")
        ).default as (opts: {
            locateFile: (file: string) => string;
        }) => Promise<unknown>;
        const { createJ2kDecoder } = await import("./dicomJ2kCodec");
        await createJ2kDecoder();
        const opts = vi.mocked(factory).mock.calls[0][0];
        expect(opts.locateFile("codec.wasm")).toBe(
            "https://cdn.example/codec.wasm",
        );
    });
});
