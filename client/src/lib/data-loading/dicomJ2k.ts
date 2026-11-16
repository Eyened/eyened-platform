/**
 * JPEG 2000 frame decode via OpenJPEG WASM.
 * Browser: parallel worker pool. Node/Vitest: main-thread fallback.
 */
import { dicomDecodeConcurrency } from "./mapPool";
import {
    createJ2kDecoder,
    decodeWithJ2kDecoder,
    type J2KDecoder,
} from "./dicomJ2kCodec";
import { J2kWorkerPool } from "./dicomJ2kPool";

let mainDecoder: Promise<J2KDecoder> | undefined;
let pool: J2kWorkerPool | undefined;
let poolFailed = false;

function useWorkers(): boolean {
    if (poolFailed || typeof Worker === "undefined") {
        return false;
    }
    // Vitest/jsdom: Worker exists but module workers + WASM are unreliable.
    if (typeof process !== "undefined" && process.env?.VITEST) {
        return false;
    }
    return typeof window !== "undefined";
}

function getPool(): J2kWorkerPool | undefined {
    if (!useWorkers()) {
        return undefined;
    }
    if (!pool) {
        try {
            pool = new J2kWorkerPool(dicomDecodeConcurrency());
        } catch {
            poolFailed = true;
            return undefined;
        }
    }
    return pool;
}

async function decodeOnMainThread(compressed: Uint8Array): Promise<Uint8Array> {
    if (!mainDecoder) {
        mainDecoder = createJ2kDecoder();
    }
    return decodeWithJ2kDecoder(await mainDecoder, compressed);
}

/** Decode one encapsulated J2K codestream to unsigned 8-bit samples. */
export async function decodeJ2kFrame(
    compressed: Uint8Array,
): Promise<Uint8Array> {
    const workerPool = getPool();
    if (workerPool) {
        try {
            return await workerPool.decode(compressed);
        } catch {
            poolFailed = true;
            pool?.terminate();
            pool = undefined;
        }
    }
    return decodeOnMainThread(compressed);
}
