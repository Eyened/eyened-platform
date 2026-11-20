import { beforeEach, describe, expect, it, vi } from "vitest";

const createJ2kDecoder = vi.fn();
const decodeWithJ2kDecoder = vi.fn();

vi.mock("./dicomJ2kCodec", () => ({
    createJ2kDecoder: (...args: unknown[]) => createJ2kDecoder(...args),
    decodeWithJ2kDecoder: (...args: unknown[]) => decodeWithJ2kDecoder(...args),
}));

describe("dicomJ2k worker", () => {
    const postMessage = vi.fn();

    beforeEach(() => {
        vi.resetModules();
        createJ2kDecoder.mockReset();
        decodeWithJ2kDecoder.mockReset();
        postMessage.mockReset();
        vi.stubGlobal("postMessage", postMessage);
        vi.stubGlobal("self", { onmessage: null, postMessage });
    });

    it("posts ready, then a decoded frame", async () => {
        createJ2kDecoder.mockResolvedValue({ name: "dec" });
        decodeWithJ2kDecoder.mockReturnValue(new Uint8Array([7, 8]));
        await import("./dicomJ2k.worker");
        await vi.waitFor(() =>
            expect(postMessage).toHaveBeenCalledWith({ type: "ready" }),
        );
        const onmessage = (
            globalThis as { self: { onmessage: (ev: MessageEvent) => void } }
        ).self.onmessage;
        const bytes = new Uint8Array([1, 2]).buffer;
        onmessage({ data: { id: 4, bytes } } as MessageEvent);
        await vi.waitFor(() => expect(postMessage).toHaveBeenCalledTimes(2));
        const payload = postMessage.mock.calls[1][0] as {
            id: number;
            bytes: ArrayBuffer;
        };
        expect(payload.id).toBe(4);
        expect(Array.from(new Uint8Array(payload.bytes))).toEqual([7, 8]);
    });

    it("posts init-error and decode errors", async () => {
        createJ2kDecoder.mockRejectedValue(new Error("wasm"));
        await import("./dicomJ2k.worker");
        await vi.waitFor(() =>
            expect(postMessage).toHaveBeenCalledWith({
                type: "init-error",
                error: "wasm",
            }),
        );
        createJ2kDecoder.mockResolvedValue({});
        decodeWithJ2kDecoder.mockImplementation(() => {
            throw "bad";
        });
        vi.resetModules();
        postMessage.mockClear();
        await import("./dicomJ2k.worker");
        await vi.waitFor(() =>
            expect(postMessage).toHaveBeenCalledWith({ type: "ready" }),
        );
        const onmessage = (
            globalThis as { self: { onmessage: (ev: MessageEvent) => void } }
        ).self.onmessage;
        onmessage({
            data: { id: 1, bytes: new ArrayBuffer(1) },
        } as MessageEvent);
        await vi.waitFor(() =>
            expect(postMessage).toHaveBeenCalledWith({
                id: 1,
                error: "bad",
            }),
        );
    });
});
