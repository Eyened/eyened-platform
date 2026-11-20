type Pending = {
    resolve: (v: Uint8Array) => void;
    reject: (e: Error) => void;
};

type WorkerSlot = {
    worker: Worker;
    ready: boolean;
    busy: boolean;
    jobId?: number;
};

/** A single frame failed to decode. The pool stays up. */
export class J2kFrameDecodeError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "J2kFrameDecodeError";
    }
}

export type J2kWorkerFactory = () => Worker;

/** Vite bundles this only when `new Worker(new URL(...))` is written literally. */
export function createJ2kWorker(): Worker {
    return new Worker(new URL("./dicomJ2k.worker.ts", import.meta.url), {
        type: "module",
    });
}

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
    private readySettled = false;
    private rejectReady: (e: Error) => void = () => {};

    constructor(
        size: number,
        createWorker: J2kWorkerFactory = createJ2kWorker,
    ) {
        const n = Math.max(1, size);
        let remaining = n;
        this.readyPromise = new Promise<void>((resolve, reject) => {
            this.rejectReady = reject;
            for (let i = 0; i < n; i++) {
                const worker = createWorker();
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
                        this.failReady(new Error(data.error));
                        return;
                    }
                    if ("type" in data && data.type === "ready") {
                        slot.ready = true;
                        if (--remaining === 0) {
                            this.readySettled = true;
                            resolve();
                        }
                        this.pump();
                        return;
                    }
                    if (!("id" in data)) {
                        return;
                    }
                    slot.busy = false;
                    slot.jobId = undefined;
                    const job = this.pending.get(data.id);
                    this.pending.delete(data.id);
                    if (!job) {
                        this.pump();
                        return;
                    }
                    if ("error" in data) {
                        job.reject(new J2kFrameDecodeError(data.error));
                    } else {
                        job.resolve(new Uint8Array(data.bytes));
                    }
                    this.pump();
                };
                worker.onerror = (ev) => {
                    const err = new Error(
                        `J2K worker failed: ${ev.message || "unknown"}`,
                    );
                    this.failReady(err);
                    this.rejectSlotJob(slot, err);
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
        const reason = new Error("J2K worker pool terminated");
        this.failReady(reason);
        for (const job of this.pending.values()) {
            job.reject(reason);
        }
        this.pending.clear();
        for (const job of this.queue) {
            job.reject(reason);
        }
        this.queue.length = 0;
        for (const slot of this.slots) {
            slot.worker.terminate();
        }
        this.slots.length = 0;
    }

    private failReady(err: Error): void {
        if (this.readySettled) {
            return;
        }
        this.readySettled = true;
        this.rejectReady(err);
    }

    private rejectSlotJob(slot: WorkerSlot, err: Error): void {
        if (slot.jobId == null) {
            return;
        }
        const job = this.pending.get(slot.jobId);
        this.pending.delete(slot.jobId);
        slot.jobId = undefined;
        slot.busy = false;
        job?.reject(err);
    }

    private pump(): void {
        while (this.queue.length > 0) {
            const slot = this.slots.find((s) => s.ready && !s.busy);
            if (!slot) {
                return;
            }
            const job = this.queue.shift()!;
            slot.busy = true;
            slot.jobId = job.id;
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
