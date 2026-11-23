import { afterEach, describe, expect, it, vi } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { Registration } from "$lib/registration/registration.svelte";
import type { ViewerContext } from "../viewerContext.svelte";
import { ETDRSGridItemOverlay } from "./ETDRSGridItemOverlay.svelte";

afterEach(() => formAnnotations.clear());

const grid = {
    image_id: "img-1",
    form_data: { fovea: { x: 100, y: 100 }, disc_edge: { x: 160, y: 100 } },
};

// Every image maps onto itself and there is no cursor.
const registration = {
    mapPosition: (_from: string, _to: string, p: unknown) => p,
    getRegistrationItem: () => undefined,
    getPosition: () => undefined,
} as unknown as Registration;

/** Repaints one grid on a synthetic 512 px viewer; returns the texts it wrote. */
function textsOf(overlay: ETDRSGridItemOverlay): string[] {
    const ctx = {
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        ellipse: vi.fn(),
        arc: vi.fn(),
        stroke: vi.fn(),
        strokeText: vi.fn(),
        fillText: vi.fn(),
        getLineDash: () => [],
        setLineDash: vi.fn(),
    };
    const viewer = {
        image: { image_id: "img-1" },
        context2D: ctx,
        viewerSize: { width: 512, height: 512 },
        imageToViewerCoordinates: (p: unknown) => p,
    } as unknown as ViewerContext;
    overlay.repaint(viewer);
    return ctx.fillText.mock.calls.map(([text]) => text as string);
}

describe("ETDRSGridItemOverlay", () => {
    it("labels the model's two points AI on the AI grid only", () => {
        formAnnotations.set(1, { id: 1, ...grid } as never);
        const settings = { radiusFraction: 0.85 };
        const ai = textsOf(
            new ETDRSGridItemOverlay(
                { kind: "snapshot", data: grid },
                registration,
                settings,
            ),
        );
        const stored = textsOf(
            new ETDRSGridItemOverlay(
                { kind: "annotation", id: 1 },
                registration,
                settings,
            ),
        );
        expect(ai.filter((text) => text === "AI")).toHaveLength(2);
        expect(stored).not.toContain("AI");
    });
});
