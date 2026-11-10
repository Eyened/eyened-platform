import { describe, expect, it, vi } from "vitest";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { viewerOf } from "./testViewer";
import type { ViewerContext } from "./viewerContext.svelte";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

describe("focusFromFit", () => {
    it("centres the point at a multiple of the fit scale, whatever the current zoom", () => {
        const viewer = viewerOf("bscan");
        viewer.viewerSize = { width: 132, height: 80 };
        viewer.initTransform();
        const fit = viewer.transform.a;
        viewer.zoom(10, 10, 7);

        viewer.focusFromFit(100, 200, 3);

        expect(viewer.transform.a).toBeCloseTo(3 * fit);
        const centre = viewer.imageToViewerCoordinates({ x: 100, y: 200 });
        expect(centre.x).toBeCloseTo(66);
        expect(centre.y).toBeCloseTo(40);
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
