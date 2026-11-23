import { describe, expect, it } from "vitest";
import { dicomDecodeConcurrency, mapPool } from "./mapPool";

describe("mapPool", () => {
    it("preserves order with limited concurrency", async () => {
        let inFlight = 0;
        let maxInFlight = 0;
        const out = await mapPool([10, 20, 30, 40, 50], 2, async (n) => {
            inFlight++;
            maxInFlight = Math.max(maxInFlight, inFlight);
            await new Promise((r) => setTimeout(r, 5));
            inFlight--;
            return n * 2;
        });
        expect(out).toEqual([20, 40, 60, 80, 100]);
        expect(maxInFlight).toBeLessThanOrEqual(2);
    });

    it("handles empty input", async () => {
        expect(await mapPool([], 4, async (x) => x)).toEqual([]);
    });
});

describe("dicomDecodeConcurrency", () => {
    it("returns a small positive pool size", () => {
        const n = dicomDecodeConcurrency();
        expect(n).toBeGreaterThanOrEqual(2);
        expect(n).toBeLessThanOrEqual(8);
    });
});
