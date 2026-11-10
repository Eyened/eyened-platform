import { describe, expect, it, vi } from "vitest";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { UpdatePosition } from "../controls/updatePosition";
import { viewerOf } from "../testViewer";
import type { ViewerEvent } from "../viewer-utils";
import { CrosshairTool, PanTool, ZoomTool } from "./viewTools";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

type Viewer = ReturnType<typeof viewerOf>;

function fitted(viewer: Viewer): Viewer {
    viewer.viewerSize = { width: 400, height: 400 };
    viewer.initTransform();
    return viewer;
}

const at = (viewer: Viewer, x: number, y: number) =>
    ({
        event: { button: 0 },
        viewerContext: viewer,
        cursor: { x, y },
        position: viewer.viewerToImageCoordinates({ x, y }),
        modifiers: { shift: false, ctrl: false, alt: false, meta: false },
    }) as unknown as ViewerEvent<PointerEvent>;

function expectAt(
    viewer: Viewer,
    image: { x: number; y: number },
    x: number,
    y: number,
) {
    const p = viewer.imageToViewerCoordinates(image);
    expect(p.x).toBeCloseTo(x);
    expect(p.y).toBeCloseTo(y);
}

describe("view tools", () => {
    it("Zoom: dragging down zooms in about the press point, up zooms out", () => {
        const viewer = fitted(viewerOf("colour"));
        const fit = viewer.transform.scale;
        const pressed = viewer.viewerToImageCoordinates({ x: 100, y: 100 });
        const zoom = new ZoomTool();
        zoom.pointerdown(at(viewer, 100, 100));
        zoom.pointermove(at(viewer, 100, 160));
        expect(viewer.transform.scale).toBeGreaterThan(fit);
        expectAt(viewer, pressed, 100, 100);
        zoom.pointermove(at(viewer, 100, 40));
        expect(viewer.transform.scale).toBeLessThan(fit);
        zoom.pointerup();
    });

    it("Pan: a click centres the clicked point; a drag moves the image with the pointer", () => {
        const viewer = fitted(viewerOf("colour"));
        const pan = new PanTool();
        const clicked = viewer.viewerToImageCoordinates({ x: 100, y: 120 });
        pan.pointerdown(at(viewer, 100, 120));
        pan.pointerup(at(viewer, 100, 120));
        expectAt(viewer, clicked, 200, 200);
        const grabbed = viewer.viewerToImageCoordinates({ x: 200, y: 200 });
        pan.pointerdown(at(viewer, 200, 200));
        pan.pointermove(at(viewer, 230, 200));
        pan.pointerup(at(viewer, 230, 200));
        expectAt(viewer, grabbed, 230, 200);
    });

    it("Cross-hair: while armed, hover leaves the crosshair and a click sets it", () => {
        const workspace = new Workspace();
        workspace.arm("crosshair");
        const viewer = fitted(viewerOf("colour", { workspace }));
        new UpdatePosition().pointermove(at(viewer, 10, 10));
        expect(viewer.registration.setPosition).not.toHaveBeenCalled();
        new CrosshairTool().pointerdown(at(viewer, 10, 10));
        expect(viewer.registration.setPosition).toHaveBeenCalledWith(
            "img-colour",
            expect.objectContaining({ index: viewer.index }),
        );
    });
});
