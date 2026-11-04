import { describe, expect, it, vi } from "vitest";
import type { ImageGET } from "../../types/openapi_types";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { ScrollOCT } from "$lib/viewer/controls/scrollOCT";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { ViewerWindowContext } from "./viewerWindowContext.svelte";

const image = { image_id: "oct-1", depth: 9 } as AbstractImage;

// The loader and the context's WebGL/canvas setup are not under test.
vi.mock("$lib/data-loading/imageLoader", () => ({
    ImageLoader: class {
        load = async () => [image];
    },
}));
vi.mock("$lib/viewer/viewerContext.svelte", () => ({
    ViewerContext: class {
        lockScroll = false;
        index = 4;
        setIndex = vi.fn();
        constructor(public image: AbstractImage) {}
    },
}));
vi.mock("$lib/registration/photoLocators", () => ({
    loadPhotoLocators: () => [],
}));

describe("strip tiles", () => {
    it("do not scroll slices", async () => {
        const registration = { addImage: vi.fn() };
        const windowContext = new ViewerWindowContext(
            { canvas: {}, clear: vi.fn() } as never,
            registration as never,
            undefined,
            [],
            { prune: vi.fn(), hydrate: vi.fn() } as never,
            {} as never,
        );
        await windowContext.loadImage({ id: "i1" } as ImageGET);
        const tile = windowContext.topViewers.get(image)! as ViewerContext;
        windowContext.destroy();

        new ScrollOCT().wheel({
            viewerContext: tile,
            wheel: { primaryDeltaPx: 100 },
        } as unknown as ViewerEvent<WheelEvent>);

        expect(tile.setIndex).not.toHaveBeenCalled();
    });
});
