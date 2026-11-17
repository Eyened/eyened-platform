import { afterEach, describe, expect, it, vi } from "vitest";

const behavior = vi.hoisted(() => ({ mode: "ok" }));

vi.mock("./dicomJ2kPool", () => ({
    J2kWorkerPool: class J2kWorkerPool {
        decode = vi.fn(async () => {
            if (behavior.mode === "throw-decode") {
                throw new Error("decode");
            }
            return new Uint8Array([5]);
        });
        terminate = vi.fn();
        constructor() {
            if (behavior.mode === "throw-ctor") {
                throw new Error("ctor");
            }
        }
    },
}));

vi.mock("./dicomJ2kCodec", () => ({
    createJ2kDecoder: vi.fn(async () => ({})),
    decodeWithJ2kDecoder: vi.fn(() => new Uint8Array([6])),
}));

describe("decodeJ2kFrame worker selection", () => {
    const savedVitest = process.env.VITEST;

    afterEach(() => {
        process.env.VITEST = savedVitest;
        behavior.mode = "ok";
        vi.unstubAllGlobals();
        vi.resetModules();
    });

    async function load() {
        return import("./dicomJ2k");
    }

    it("stays on the main thread under Vitest", async () => {
        vi.stubGlobal("Worker", class {});
        const { decodeJ2kFrame } = await load();
        expect(Array.from(await decodeJ2kFrame(new Uint8Array([1])))).toEqual([
            6,
        ]);
    });

    it("uses the pool in a browser and falls back when it fails", async () => {
        delete process.env.VITEST;
        vi.stubGlobal("Worker", class {});
        behavior.mode = "ok";
        const { decodeJ2kFrame } = await load();
        expect(Array.from(await decodeJ2kFrame(new Uint8Array([1])))).toEqual([
            5,
        ]);

        vi.resetModules();
        behavior.mode = "throw-ctor";
        const ctor = await load();
        expect(
            Array.from(await ctor.decodeJ2kFrame(new Uint8Array([1]))),
        ).toEqual([6]);

        vi.resetModules();
        behavior.mode = "throw-decode";
        const failing = await load();
        expect(
            Array.from(await failing.decodeJ2kFrame(new Uint8Array([1]))),
        ).toEqual([6]);
    });
});
