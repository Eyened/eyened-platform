import { describe, expect, it, vi } from "vitest";
import type { LoadedImages } from "$lib/data-loading/imageLoader";
import { instances } from "$lib/data/stores.svelte";
import type { ImageGET } from "../../types/openapi_types";
import { ViewerWindowContext } from "./viewerWindowContext.svelte";

// The loader and the context's WebGL/canvas setup are not under test.
vi.mock("$lib/data-loading/imageLoader", () => ({
    ImageLoader: class {
        load = async () => [];
    },
}));

const instance = (id: string) =>
    ({
        id,
        segmentations: [],
        patient: { identifier: "P-000417" },
        study: { date: "2023-05-04" },
        modality: "OCT",
        laterality: "R",
        device: {},
    }) as unknown as ImageGET;

describe("setInstanceIDs", () => {
    it("keeps the images that loaded when another load fails", async () => {
        const addImages = vi.fn();
        const ctx = new ViewerWindowContext(
            { canvas: {}, clear: vi.fn() } as never,
            {} as never,
            undefined,
            [],
            { prune: vi.fn(), hydrate: vi.fn(), addImages } as never,
            {} as never,
        );
        instances.set("i1", instance("i1"));
        instances.set("i2", instance("i2"));
        vi.spyOn(ctx, "loadImage").mockImplementation(async (inst) => {
            if (inst.id === "i1") throw new Error("decode failed");
            return [
                { image_id: "img-2", instance: inst },
            ] as unknown as LoadedImages;
        });
        const error = vi.spyOn(console, "error").mockImplementation(() => {});

        const entries = await ctx.setInstanceIDs(["i1", "i2"]);
        ctx.destroy();

        expect(addImages).toHaveBeenCalledWith(entries);
        expect(entries.map((e) => e.imageId)).toEqual(["img-2"]);
        expect(error).toHaveBeenCalledWith("Loading instance i1 failed");
    });
});
