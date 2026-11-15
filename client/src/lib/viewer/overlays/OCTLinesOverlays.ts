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
        const volumes = lineVolumes(here);
        paintOutlines(context2D, viewerContext, volumes);
        const otherStyles = Object.fromEntries(
            Object.entries(volumes).map(([id, volume]) => [
                id,
                otherLineStyle(screenGap(viewerContext, volume)),
            ]),
        );
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
                    // Uncased, so up to 193 lines do not black out the macula.
                    const style =
                        otherStyles[locator.octImageId] ?? otherLineStyle(0);
                    context2D.lineWidth = style.width;
                    context2D.strokeStyle = style.colour;
                    locator.paint(context2D, viewerContext);
                }
            } catch (error) {
                console.warn("PhotoLocator overlay paint failed", error);
            }
        }
    }
}

/** Each volume's line B-scans in scan order; circle scans and single lines are left out. */
function lineVolumes(
    locators: PhotoLocator[],
): Record<string, LinePhotoLocator[]> {
    const byVolume: Record<string, LinePhotoLocator[]> = {};
    for (const locator of locators) {
        if (!(locator instanceof LinePhotoLocator)) continue;
        (byVolume[locator.octImageId] ??= []).push(locator);
    }
    for (const [id, volume] of Object.entries(byVolume)) {
        if (volume.length < 2) delete byVolume[id];
        else volume.sort((a, b) => a.index - b.index);
    }
    return byVolume;
}

/** On-screen distance between neighbouring B-scans of one volume. */
function screenGap(
    viewerContext: ViewerContext,
    volume: LinePhotoLocator[],
): number {
    const a = viewerContext.imageToViewerCoordinates(volume[0].start);
    const b = viewerContext.imageToViewerCoordinates(
        volume[volume.length - 1].start,
    );
    return Math.hypot(b.x - a.x, b.y - a.y) / (volume.length - 1);
}

/** Crowded lines (gap 2 px or less) stay faint hairlines; wider gaps get 1 px, rising to 60 % at 8 px. */
function otherLineStyle(gap: number): { width: number; colour: string } {
    if (!(gap > 2)) return { width: 0.5, colour: FAINT };
    const alpha = Math.min(0.6, 0.2 + ((gap - 2) * 0.4) / 6);
    return {
        width: 1,
        colour: `rgba(0,255,0,${Math.round(alpha * 100) / 100})`,
    };
}

/** Each volume's scanned area: its first and last B-scan lines joined at their ends. */
function paintOutlines(
    ctx: CanvasRenderingContext2D,
    viewerContext: ViewerContext,
    volumes: Record<string, LinePhotoLocator[]>,
) {
    ctx.lineWidth = 1;
    ctx.strokeStyle = OUTLINE;
    for (const volume of Object.values(volumes)) {
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
