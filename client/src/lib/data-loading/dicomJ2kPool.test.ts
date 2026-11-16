import { afterEach, describe, expect, it, vi } from "vitest";
import { J2kWorkerPool } from "./dicomJ2kPool";

class FakeWorker {
    static instances: FakeWorker[] = [];
    static inFlight = 0;
    static maxInFlight = 0;
    onmessage: ((ev: MessageEvent) => void) | null = null;
    onerror: ((ev: ErrorEvent) => void) | null = null;

    constructor(_url: URL | string, _opts?: WorkerOptions) {
        FakeWorker.instances.push(this);
        queueMicrotask(() => {
            this.onmessage?.({ data: { type: "ready" } } as MessageEvent);
        });
    }

    postMessage(data: { id: number; bytes: ArrayBuffer }) {
        const id = data.id;
        const len = data.bytes.byteLength;
        FakeWorker.inFlight++;
        FakeWorker.maxInFlight = Math.max(
            FakeWorker.maxInFlight,
            FakeWorker.inFlight,
        );
        setTimeout(() => {
            FakeWorker.inFlight--;
            const out = new Uint8Array(len).fill(len & 0xff);
            this.onmessage?.({
                data: { id, bytes: out.buffer },
            } as MessageEvent);
        }, 20);
    }

    terminate() {}
}

describe("J2kWorkerPool", () => {
    afterEach(() => {
        FakeWorker.instances = [];
        FakeWorker.inFlight = 0;
        FakeWorker.maxInFlight = 0;
        vi.unstubAllGlobals();
    });

    it("decodes frames in parallel across workers", async () => {
        vi.stubGlobal("Worker", FakeWorker);
        const pool = new J2kWorkerPool(
            3,
            () => new URL("./dicomJ2k.worker.ts", import.meta.url),
        );
        const results = await Promise.all([
            pool.decode(new Uint8Array([1])),
            pool.decode(new Uint8Array([1, 2])),
            pool.decode(new Uint8Array([1, 2, 3])),
        ]);
        expect(FakeWorker.instances).toHaveLength(3);
        expect(FakeWorker.maxInFlight).toBe(3);
        expect(results.map((r) => r.length)).toEqual([1, 2, 3]);
        pool.terminate();
    });
});
