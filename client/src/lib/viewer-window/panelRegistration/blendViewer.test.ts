import { instances } from "$lib/data";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

vi.mock("$lib/viewer/Viewer.svelte", () => ({ default: () => null }));

const { registeredImageSize } = await import("./blendViewer");

const open = {
    image_id: "open",
    width: 20,
    height: 10,
} as unknown as AbstractImage;

const context = {
    topViewers: new Map([[open, {}]]),
} as unknown as ViewerWindowContext;

describe("registeredImageSize", () => {
    afterEach(() => {
        instances.clear();
    });

    it("prefers an open image, then the instance, then nothing", () => {
        instances.set("closed", { columns: 30, rows: 40 } as never);
        instances.set("empty", { columns: 0, rows: 0 } as never);

        expect(registeredImageSize(context, "open")).toEqual([20, 10]);
        expect(registeredImageSize(context, "closed")).toEqual([30, 40]);
        expect(registeredImageSize(context, "empty")).toBeUndefined();
        expect(registeredImageSize(context, "missing")).toBeUndefined();
    });
});
