import {
    LinePhotoLocator,
    type PhotoLocator,
} from "$lib/registration/photoLocators";
import type { RenderTarget } from "$lib/webgl/types";
import type { LocalizerMode } from "$lib/workspace/workspaceRules";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

const FAINT = "rgba(0,255,0,0.2)";
const CURRENT = "rgba(255,255,255,1)";

export class OCTLinesOverlay implements Overlay {
    constructor(
        readonly photolocators: PhotoLocator[],
        private readonly mode: () => LocalizerMode = () => "all",
    ) {}

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const mode = this.mode();
        if (mode === "off") return;
        const { context2D, image } = viewerContext;
        const here = this.photolocators.filter(
            (locator) => locator.enfaceImageId == image.image_id,
        );
        context2D.lineWidth = 0.5;
        if (mode === "current") paintOutlines(context2D, viewerContext, here);
        for (const locator of here) {
            const octPosition = viewerContext.registration.getPosition(
                locator.octImageId,
            );
            const current = octPosition?.index == locator.index;
            if (mode === "current" && !current) continue;
            context2D.strokeStyle = current ? CURRENT : FAINT;
            try {
                locator.paint(context2D, viewerContext);
            } catch (error) {
                console.warn("PhotoLocator overlay paint failed", error);
            }
        }
    }
}

/** Each volume's scanned area: its first and last B-scan lines joined at their ends. Circle scans get none. */
function paintOutlines(
    ctx: CanvasRenderingContext2D,
    viewerContext: ViewerContext,
    locators: PhotoLocator[],
) {
    const byVolume: Record<string, LinePhotoLocator[]> = {};
    for (const locator of locators) {
        if (!(locator instanceof LinePhotoLocator)) continue;
        (byVolume[locator.octImageId] ??= []).push(locator);
    }
    ctx.strokeStyle = FAINT;
    for (const volume of Object.values(byVolume)) {
        if (volume.length < 2) continue;
        volume.sort((a, b) => a.index - b.index);
        const first = volume[0];
        const last = volume[volume.length - 1];
        const corners = [first.start, first.end, last.end, last.start].map(
            (p) => viewerContext.imageToViewerCoordinates(p),
        );
        ctx.beginPath();
        ctx.moveTo(corners[0].x, corners[0].y);
        for (const c of corners.slice(1)) ctx.lineTo(c.x, c.y);
        ctx.closePath();
        ctx.stroke();
    }
}
