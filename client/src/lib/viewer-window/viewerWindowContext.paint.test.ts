import type { Registration } from "$lib/registration/registration.svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ViewerWindowContext } from "./viewerWindowContext.svelte";

function createContext() {
    const webgl = {
        clear: vi.fn(),
        canvas: { width: 8, height: 8 },
    };
    return new ViewerWindowContext(
        webgl as never,
        {} as Registration,
        null,
        [],
    );
}

describe("ViewerWindowContext registration editor paint", () => {
    let ctx: ViewerWindowContext | undefined;

    beforeEach(() => {
        vi.stubGlobal(
            "requestAnimationFrame",
            vi.fn(() => 1),
        );
        vi.stubGlobal("cancelAnimationFrame", vi.fn());
    });

    afterEach(() => {
        ctx?.destroy();
        ctx = undefined;
        vi.unstubAllGlobals();
    });

    it("paints foreground viewers while the editor is open, then resumes the others", () => {
        const background = { repaint: vi.fn() };
        const editorViewer = { repaint: vi.fn() };
        ctx = createContext();
        ctx.addViewer(background as never);

        ctx.openRegistrationEditor({ imageIds: ["a", "b"], annotationId: 21 });
        ctx.addViewer(editorViewer as never, true);

        ctx.repaint();
        expect(background.repaint).not.toHaveBeenCalled();
        expect(editorViewer.repaint).toHaveBeenCalledOnce();

        ctx.closeRegistrationEditor();
        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(ctx.registrationEditor).toBeNull();
    });

    it("paints foreground viewers while a series blend is open, then resumes the others", () => {
        const background = { repaint: vi.fn() };
        const blendViewer = { repaint: vi.fn() };
        ctx = createContext();
        ctx.addViewer(background as never);

        ctx.openSeriesBlend({ imageIds: ["a", "b", "c"] });
        ctx.addViewer(blendViewer as never, true);

        ctx.repaint();
        expect(background.repaint).not.toHaveBeenCalled();
        expect(blendViewer.repaint).toHaveBeenCalledOnce();

        ctx.closeSeriesBlend();
        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(ctx.seriesBlend).toBeNull();
    });

    it("keeps a window viewer out of the paint list while foreground is active", () => {
        const late = { repaint: vi.fn() };
        const foreground = { repaint: vi.fn() };
        ctx = createContext();
        ctx.openSeriesBlend({ imageIds: ["a", "b"] });
        ctx.addViewer(late as never);
        ctx.addViewer(foreground as never, true);

        ctx.repaint();
        expect(late.repaint).not.toHaveBeenCalled();
        expect(foreground.repaint).toHaveBeenCalledOnce();
    });

    it("paints a foreground viewer that was added before the session opened", () => {
        const background = { repaint: vi.fn() };
        const foreground = { repaint: vi.fn() };
        ctx = createContext();
        ctx.addViewer(background as never);
        ctx.addViewer(foreground as never, true);

        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(foreground.repaint).not.toHaveBeenCalled();

        ctx.openSeriesBlend({ imageIds: ["a", "b"] });
        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(foreground.repaint).toHaveBeenCalledOnce();
    });
});

vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));
vi.mock("./MainViewer.svelte", () => ({ default: {} }));
