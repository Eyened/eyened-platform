import {
    LinePhotoLocator,
    type PhotoLocator,
} from "$lib/registration/photoLocators";
import type { RenderTarget } from "$lib/webgl/types";
import type { LocalizerMode } from "$lib/workspace/workspaceRules";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { cased } from "./casing";

const FAINT = "rgba(0,255,0,0.2)";
// ASSUMPTION: the outline is 1 px like the current line; the design gives no width.
const OUTLINE = "rgb(0,255,0)";
const CURRENT = "rgb(255,255,255)";

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
        if (mode === "current") paintOutlines(context2D, viewerContext, here);
        for (const locator of here) {
            const octPosition = viewerContext.registration.getPosition(
                locator.octImageId,
            );
            const current = octPosition?.index == locator.index;
            if (mode === "current" && !current) continue;
            try {
                if (current) {
                    context2D.lineWidth = 1;
                    context2D.strokeStyle = CURRENT;
                    cased(context2D, () =>
                        locator.paint(context2D, viewerContext),
                    );
                } else {
                    // All mode's other B-scans stay faint and uncased, so up to 193 lines do not black out the macula.
                    context2D.lineWidth = 0.5;
                    context2D.strokeStyle = FAINT;
                    locator.paint(context2D, viewerContext);
                }
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
    ctx.lineWidth = 1;
    ctx.strokeStyle = OUTLINE;
    for (const volume of Object.values(byVolume)) {
        if (volume.length < 2) continue;
        volume.sort((a, b) => a.index - b.index);
        const first = volume[0];
        const last = volume[volume.length - 1];
        const corners = [first.start, first.end, last.end, last.start].map(
            (p) => viewerContext.imageToViewerCoordinates(p),
        );
        cased(ctx, () => {
            ctx.beginPath();
            ctx.moveTo(corners[0].x, corners[0].y);
            for (const c of corners.slice(1)) ctx.lineTo(c.x, c.y);
            ctx.closePath();
            ctx.stroke();
        });
    }
}
