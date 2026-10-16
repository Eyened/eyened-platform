import { describe, expect, it } from "vitest";
import { blendLayers, selectFixedImage } from "./blendLayers";

const always = () => true;
const never = () => false;

describe("blendLayers", () => {
    it("draws the fixed image and a checked image that has a path", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: ["b"],
            hasPath: always,
            canSample: always,
        });
        expect(layers.map((l) => [l.imageId, l.role, l.draw, l.colour])).toEqual([
            ["a", "fixed", true, [1, 0, 0]],
            ["b", "overlay", true, [0, 1, 1]],
        ]);
    });

    it("keeps a colour for a checked image with no path and does not draw it", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b", "c"],
            fixedImageId: "a",
            overlayImageIds: ["b", "c"],
            hasPath: (id) => id === "c",
            canSample: always,
        });
        expect(layers.map((l) => [l.imageId, l.draw, l.colour])).toEqual([
            ["a", true, [1, 0, 0]],
            ["b", false, [0, 1, 0]],
            ["c", true, [0, 0, 1]],
        ]);
    });

    it("drops an unchecked image and reassigns colours", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b", "c"],
            fixedImageId: "a",
            overlayImageIds: ["c"],
            hasPath: always,
            canSample: always,
        });
        expect(layers.map((l) => l.imageId)).toEqual(["a", "c"]);
        expect(layers.map((l) => l.colour)).toEqual([
            [1, 0, 0],
            [0, 1, 1],
        ]);
    });

    it("leaves a lone fixed image untinted", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: [],
            hasPath: always,
            canSample: always,
        });
        expect(layers).toEqual([
            { imageId: "a", role: "fixed", colour: [1, 1, 1], untinted: true, draw: true },
        ]);
    });

    it("does not draw an image that cannot be sampled", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: ["b"],
            hasPath: always,
            canSample: (id) => id === "a",
        });
        expect(layers.find((l) => l.imageId === "b")?.draw).toBe(false);
        expect(layers.find((l) => l.imageId === "b")?.colour).toEqual([0, 1, 1]);
    });

    it("does not draw a fixed image that cannot be sampled", () => {
        const layers = blendLayers({
            orderedImageIds: ["vol"],
            fixedImageId: "vol",
            overlayImageIds: [],
            hasPath: never,
            canSample: never,
        });
        expect(layers[0]?.draw).toBe(false);
    });
});

describe("selectFixedImage", () => {
    it("keeps the previous fixed image as a checked overlay", () => {
        expect(selectFixedImage({ fixedImageId: "a", overlayImageIds: ["b", "c"] }, "b")).toEqual({
            fixedImageId: "b",
            overlayImageIds: ["c", "a"],
        });
    });
});
