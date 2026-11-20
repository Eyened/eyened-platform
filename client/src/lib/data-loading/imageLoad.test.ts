import { describe, expect, it } from "vitest";
import { ImageLoad } from "./imageLoad.svelte";

describe("ImageLoad", () => {
    it("starts on Downloading and finishes with the loader result", async () => {
        const load = new ImageLoad(async (progress) => {
            progress.loading!.message = "Decoding…";
            return 7;
        });
        await expect(load.promise).resolves.toBe(7);
        expect(load.message).toBe("Decoding…");
    });
});
