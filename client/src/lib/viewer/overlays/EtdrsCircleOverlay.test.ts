import { describe, expect, it, vi } from "vitest";
import type { Scale } from "$lib/layers/imageScale";
import type { Registration } from "$lib/registration/registration.svelte";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { EtdrsCircleOverlay } from "./EtdrsCircleOverlay";

function viewer() {
    return {
        image: { image_id: "img-1" },
        context2D: {
            beginPath: vi.fn(),
            ellipse: vi.fn(),
            stroke: vi.fn(),
            getLineDash: () => [],
            setLineDash: vi.fn(),
        },
        imageToViewerCoordinates: (p: unknown) => p,
        claimCursor: vi.fn(),
    } as unknown as ViewerContext;
}

// The shared pointer is at (50, 60) in this image.
const registration = {
    getPosition: () => ({ x: 50, y: 60, index: 0 }),
} as unknown as Registration;

describe("EtdrsCircleOverlay", () => {
    it("draws the chosen size at the shared pointer from this image's scale and hides the cursor; without a scale, nothing", () => {
        let scale: Scale | null = {
            x: 10,
            y: 10,
            source: "stored",
            pick: { kind: "stored" },
        };
        const overlay = new EtdrsCircleOverlay(
            registration,
            () => "C2",
            () => scale,
        );
        const v = viewer();
        overlay.repaint(v);
        // C2 is a quarter of the 1 mm central circle: 250 µm across, so a 12.5 px radius at 10 µm/px.
        expect(v.context2D.ellipse).toHaveBeenCalledWith(
            50,
            60,
            12.5,
            12.5,
            0,
            0,
            2 * Math.PI,
        );
        expect(v.claimCursor).toHaveBeenCalledWith("none", CursorPriority.Hide);
        scale = null;
        const bare = viewer();
        overlay.repaint(bare);
        expect(bare.context2D.ellipse).not.toHaveBeenCalled();
        expect(bare.claimCursor).not.toHaveBeenCalled();
    });
});
