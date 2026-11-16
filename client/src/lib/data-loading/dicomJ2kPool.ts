type Pending = {
    resolve: (v: Uint8Array) => void;
    reject: (e: Error) => void;
};

type WorkerSlot = {
    worker: Worker;
    ready: boolean;
    busy: boolean;
};

/**
 * Fixed-size pool of J2K decode workers. Copies input before transfer so
 * views into the parent DICOM buffer are not detached.
 */
export class J2kWorkerPool {
    private readonly slots: WorkerSlot[] = [];
    private readonly pending = new Map<number, Pending>();
    private readonly queue: Array<{
        id: number;
        bytes: Uint8Array;
        resolve: (v: Uint8Array) => void;
        reject: (e: Error) => void;
    }> = [];
    private nextId = 1;
    private readyPromise: Promise<void>;

    constructor(
        size: number,
        workerUrl: () => URL = () =>
            new URL("./dicomJ2k.worker.ts", import.meta.url),
    ) {
        const n = Math.max(1, size);
        let remaining = n;
        this.readyPromise = new Promise<void>((resolve, reject) => {
            for (let i = 0; i < n; i++) {
                const worker = new Worker(workerUrl(), { type: "module" });
                const slot: WorkerSlot = {
                    worker,
                    ready: false,
                    busy: false,
                };
                this.slots.push(slot);
                worker.onmessage = (ev: MessageEvent) => {
                    const data = ev.data as
                        | { type: "ready" }
                        | { type: "init-error"; error: string }
                        | { id: number; bytes: ArrayBuffer }
                        | { id: number; error: string };
                    if ("type" in data && data.type === "init-error") {
                        reject(new Error(data.error));
                        return;
                    }
                    if ("type" in data && data.type === "ready") {
                        slot.ready = true;
                        if (--remaining === 0) {
                            resolve();
                        }
                        this.pump();
                        return;
                    }
                    if (!("id" in data)) {
                        return;
                    }
                    slot.busy = false;
                    const job = this.pending.get(data.id);
                    this.pending.delete(data.id);
                    if (!job) {
                        this.pump();
                        return;
                    }
                    if ("error" in data) {
                        job.reject(new Error(data.error));
                    } else {
                        job.resolve(new Uint8Array(data.bytes));
                    }
                    this.pump();
                };
                worker.onerror = (ev) => {
                    reject(
                        new Error(
                            `J2K worker failed: ${ev.message || "unknown"}`,
                        ),
                    );
                };
            }
        });
    }

    async decode(compressed: Uint8Array): Promise<Uint8Array> {
        await this.readyPromise;
        return new Promise<Uint8Array>((resolve, reject) => {
            const id = this.nextId++;
            // Copy: compressed may be a view into the full DICOM ArrayBuffer.
            this.queue.push({
                id,
                bytes: compressed.slice(),
                resolve,
                reject,
            });
            this.pump();
        });
    }

    terminate(): void {
        for (const slot of this.slots) {
            slot.worker.terminate();
        }
        this.slots.length = 0;
        for (const job of this.queue) {
            job.reject(new Error("J2K worker pool terminated"));
        }
        this.queue.length = 0;
    }

    private pump(): void {
        while (this.queue.length > 0) {
            const slot = this.slots.find((s) => s.ready && !s.busy);
            if (!slot) {
                return;
            }
            const job = this.queue.shift()!;
            slot.busy = true;
            this.pending.set(job.id, {
                resolve: job.resolve,
                reject: job.reject,
            });
            const buf = job.bytes.buffer.slice(
                job.bytes.byteOffset,
                job.bytes.byteOffset + job.bytes.byteLength,
            );
            slot.worker.postMessage({ id: job.id, bytes: buf }, [buf]);
        }
    }
}
