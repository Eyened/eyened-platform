import { describe, expect, it, vi } from "vitest";
import { viewerOf } from "./testViewer";

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
