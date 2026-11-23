import { describe, expect, it, vi } from "vitest";
import { setLoadMessage, type ImageLoadState } from "./loadProgress";

describe("setLoadMessage", () => {
    it("updates loading.message when present", () => {
        const loading: ImageLoadState = { message: "Downloading…" };
        setLoadMessage({ loading }, "Decoding…");
        expect(loading.message).toBe("Decoding…");
    });

    it("no-ops without a loading object", () => {
        expect(() => setLoadMessage({}, "Decoding…")).not.toThrow();
        expect(() => setLoadMessage(undefined, "Decoding…")).not.toThrow();
    });
});

describe("ImageLoader DICOM progress messages", () => {
    it("sets Downloading then Decoding around fetch+decode", async () => {
        vi.resetModules();
        const decodeDicomBuffer = vi.fn(async () => ({
            volume: new Uint8Array(1),
            dimensions: {
                width: 1,
                height: 1,
                depth: 1,
                width_mm: -1,
                height_mm: -1,
                depth_mm: -1,
            },
            meta: {},
        }));
        vi.doMock("./dicomDecoder", () => ({ decodeDicomBuffer }));

        const messages: string[] = [];
        const fetchMock = vi.fn(async () => {
            messages.push("fetch");
            return {
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8),
            };
        });
        vi.stubGlobal("fetch", fetchMock);

        const { ImageLoader } = await import("./imageLoader");
        const loader = new ImageLoader({} as never);
        const loading: ImageLoadState = { message: "Downloading…" };
        // Intercept message writes
        const proxied = {
            get message() {
                return loading.message;
            },
            set message(v: string) {
                messages.push(v);
                loading.message = v;
            },
        };

        await loader.decodeDicomVolume("https://example.test/a.dcm", "img", {
            loading: proxied,
        });

        expect(messages).toEqual(["Downloading…", "fetch", "Decoding…"]);
        expect(decodeDicomBuffer).toHaveBeenCalledOnce();
        vi.unstubAllGlobals();
        vi.doUnmock("./dicomDecoder");
    });
});
