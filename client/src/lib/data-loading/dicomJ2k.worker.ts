/// <reference lib="webworker" />
import { createJ2kDecoder, decodeWithJ2kDecoder } from "./dicomJ2kCodec";

let decoderPromise = createJ2kDecoder();

decoderPromise
    .then(() => postMessage({ type: "ready" }))
    .catch((err) =>
        postMessage({
            type: "init-error",
            error: err instanceof Error ? err.message : String(err),
        }),
    );

self.onmessage = async (ev: MessageEvent) => {
    const { id, bytes } = ev.data as { id: number; bytes: ArrayBuffer };
    try {
        const decoder = await decoderPromise;
        const out = decodeWithJ2kDecoder(decoder, new Uint8Array(bytes));
        const copy = out.slice();
        postMessage({ id, bytes: copy.buffer }, [copy.buffer]);
    } catch (err) {
        postMessage({
            id,
            error: err instanceof Error ? err.message : String(err),
        });
    }
};
