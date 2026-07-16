import { describe, it, expect, vi } from "vitest";
import { getFdsRegistration } from "./fdsRegistration";
import { parseHeidelbergPhotoLocator } from "./parsePhotoLocator";
import { CirclePhotoLocator } from "./photoLocators";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

/** Real PhotoLocators attribute payload that previously crashed the viewer (wd0jshs1). */
const WD0JSHS1_CIRCLE = {
    type: "CirclePhotoLocator",
    index: 0,
    center: { x: 1197, y: 917 },
    radius: 216,
    image_id: "50a52xx4",
    start_angle: Math.PI,
};

function mockOctImage(photoLocators: unknown[], octId = 999, width = 768) {
    return {
        width,
        instance: {
            id: octId,
            attrs: { PhotoLocators: photoLocators },
        },
    } as unknown as AbstractImage;
}

describe("getFdsRegistration", () => {
    it("loads circle scan locators from attribute JSON center field", () => {
        const locators = getFdsRegistration(mockOctImage([WD0JSHS1_CIRCLE]));

        expect(locators).toHaveLength(1);
        const locator = locators[0] as CirclePhotoLocator;
        expect(locator).toBeInstanceOf(CirclePhotoLocator);
        expect(locator.enfaceImageId).toBe("50a52xx4");
        expect(locator.octImageId).toBe("999");
        expect(locator.center).toEqual({ x: 1197, y: 917 });
        expect(locator.radius).toBe(216);
    });

    it("skips invalid entries instead of returning locators with undefined center", () => {
        const locators = getFdsRegistration(
            mockOctImage([
                {
                    type: "CirclePhotoLocator",
                    index: 0,
                    radius: 216,
                    image_id: "50a52xx4",
                    start_angle: Math.PI,
                },
            ]),
        );

        expect(locators).toHaveLength(0);
    });

    it("keeps valid entries when another entry in the array is invalid", () => {
        const locators = getFdsRegistration(
            mockOctImage([{ type: "Unknown", index: 0 }, WD0JSHS1_CIRCLE]),
        );

        expect(locators).toHaveLength(1);
        expect((locators[0] as CirclePhotoLocator).center).toEqual({
            x: 1197,
            y: 917,
        });
    });
});

describe("parseHeidelbergPhotoLocator", () => {
    it("infers a CirclePhotoLocator from legacy centre + injected type/image_id/index", () => {
        const item = parseHeidelbergPhotoLocator(
            { centre: { x: 1197, y: 917 }, radius: 216, start_angle: Math.PI },
            "enface-1",
            3,
        );
        expect(item).toEqual({
            type: "CirclePhotoLocator",
            image_id: "enface-1",
            index: 3,
            center: { x: 1197, y: 917 },
            radius: 216,
            start_angle: Math.PI,
        });
    });

    it("infers a LinePhotoLocator when start/end are present", () => {
        const item = parseHeidelbergPhotoLocator(
            { start: { x: 0, y: 0 }, end: { x: 10, y: 10 } },
            "enface-1",
            0,
        );
        expect(item?.type).toBe("LinePhotoLocator");
    });

    it("returns null (skips) when neither line nor circle fields are valid", () => {
        expect(
            parseHeidelbergPhotoLocator({ radius: 216 }, "enface-1", 0),
        ).toBeNull();
    });
});

describe("CirclePhotoLocator.paint", () => {
    it("does not throw when center is defined", () => {
        const locator = new CirclePhotoLocator(
            "50a52xx4",
            "999",
            { x: 1197, y: 917 },
            216,
            Math.PI,
            0,
            768,
        );

        const ctx = {
            beginPath: vi.fn(),
            ellipse: vi.fn(),
            stroke: vi.fn(),
        } as unknown as CanvasRenderingContext2D;

        const viewerContext = {
            imageToViewerCoordinates: ({ x, y }: { x: number; y: number }) => ({
                x,
                y,
            }),
        } as ViewerContext;

        expect(() => locator.paint(ctx, viewerContext)).not.toThrow();
        expect(ctx.ellipse).toHaveBeenCalled();
    });

    it("no-ops when center is missing", () => {
        const locator = new CirclePhotoLocator(
            "50a52xx4",
            "999",
            undefined as unknown as { x: number; y: number },
            216,
            Math.PI,
            0,
            768,
        );

        const ctx = {
            beginPath: vi.fn(),
            ellipse: vi.fn(),
            stroke: vi.fn(),
        } as unknown as CanvasRenderingContext2D;

        const viewerContext = {
            imageToViewerCoordinates: vi.fn(),
        } as unknown as ViewerContext;

        locator.paint(ctx, viewerContext);

        expect(viewerContext.imageToViewerCoordinates).not.toHaveBeenCalled();
        expect(ctx.ellipse).not.toHaveBeenCalled();
    });
});
