import { instances } from "$lib/data";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { afterEach, describe, expect, it } from "vitest";
import { registeredImageSize } from "./blendStyles";

const open = {
    image_id: "open",
    width: 20,
    height: 10,
} as unknown as AbstractImage;
const win = { topViewers: new Map([[open, {}]]) } as never;

afterEach(() => instances.clear());

describe("registeredImageSize", () => {
    it("prefers an open image, then the instance, then nothing", () => {
        instances.set("closed", { columns: 30, rows: 40 } as never);
        instances.set("empty", { columns: 0, rows: 0 } as never);
        expect(registeredImageSize(win, "open")).toEqual([20, 10]);
        expect(registeredImageSize(win, "closed")).toEqual([30, 40]);
        expect(registeredImageSize(win, "empty")).toBeUndefined();
        expect(registeredImageSize(win, "missing")).toBeUndefined();
    });
});
