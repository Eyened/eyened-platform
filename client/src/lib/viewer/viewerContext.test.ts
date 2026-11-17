import { describe, expect, it, vi } from "vitest";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { viewerOf } from "./testViewer";
import type { ViewerContext } from "./viewerContext.svelte";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

describe("focusFrom", () => {
    it("centres an image point at a multiple of the source viewer's on-screen scale", () => {
        const source = viewerOf("bscan");
        source.viewerSize = { width: 400, height: 300 };
        source.initTransform();
        source.zoom(10, 10, 1.7);
        const panel = viewerOf("bscan");
        panel.viewerSize = { width: 260, height: 260 };

        panel.focusFrom(source, 100, 200, 3);

        expect(panel.imageViewerTransform.a).toBeCloseTo(
            3 * source.imageViewerTransform.a,
        );
        expect(panel.imageViewerTransform.e).toBeCloseTo(
            3 * source.imageViewerTransform.e,
        );
        const centre = panel.imageToViewerCoordinates({ x: 100, y: 200 });
        expect(centre.x).toBeCloseTo(130);
        expect(centre.y).toBeCloseTo(130);
    });
});

/** Puts the crosshair on a slice of this viewer's image. */
function crosshairAt(viewer: ViewerContext, index: number) {
    vi.mocked(
        viewer.viewerWindowContext.registration.getPosition,
    ).mockReturnValue({ x: 1, y: 2, index });
}

describe("syncIndex", () => {
    it("holds a locked image's slice, also in a viewport rebuilt for it; a drawing tool's scroll block holds nothing", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("bscan", { workspace });
        viewer.lockScroll = true;
        crosshairAt(viewer, 10);
        viewer.syncIndex();
        expect(viewer.index).toBe(10);

        workspace.setLocked("img-bscan", true);
        crosshairAt(viewer, 20);
        viewer.syncIndex();
        expect(viewer.index).toBe(10);

        const rebuilt = viewerOf("bscan", { workspace });
        crosshairAt(rebuilt, 20);
        rebuilt.syncIndex();
        expect(rebuilt.index).toBe(64);
    });

    it("moves a strip tile's slice only while Crosshair tracking is on", () => {
        const workspace = new Workspace();
        const tile = viewerOf("bscan", { workspace, tile: true });
        crosshairAt(tile, 30);
        tile.syncIndex();
        expect(tile.index).toBe(30);

        workspace.stripTracking = false;
        crosshairAt(tile, 40);
        tile.syncIndex();
        expect(tile.index).toBe(30);
    });
});

describe("projection start mode", () => {
    it("starts an OCT's own projection in Mask and other images Off", () => {
        expect(
            viewerOf("grey", { imageId: "oct-1_proj" }).enfaceProjectionMode,
        ).toBe("binary");
        expect(viewerOf("grey").enfaceProjectionMode).toBe("off");
    });
});
