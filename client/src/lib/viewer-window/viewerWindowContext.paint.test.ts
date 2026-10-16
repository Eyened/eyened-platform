import { describe, expect, it, vi } from "vitest";
import { ViewerWindowContext } from "./viewerWindowContext.svelte";

function contextWith(viewers: { repaint: ReturnType<typeof vi.fn> }[]) {
    const ctx = Object.create(ViewerWindowContext.prototype) as ViewerWindowContext & {
        viewers: Set<unknown>;
        editorViewers: Set<unknown> | null;
        webgl: { clear: ReturnType<typeof vi.fn>; canvas: { width: number; height: number } };
    };
    ctx.viewers = new Set(viewers);
    ctx.editorViewers = null;
    ctx.registrationEditor = null;
    ctx.webgl = { clear: vi.fn(), canvas: { width: 8, height: 8 } };
    return ctx;
}

describe("ViewerWindowContext registration editor paint", () => {
    it("paints only viewers added during the session, then resumes the others", () => {
        const background = { repaint: vi.fn() };
        const editorViewer = { repaint: vi.fn() };
        const ctx = contextWith([background]);

        ctx.openRegistrationEditor({ imageIds: ["a", "b"], annotationId: 21 });
        ctx.addViewer(editorViewer as never);

        ctx.repaint();
        expect(background.repaint).not.toHaveBeenCalled();
        expect(editorViewer.repaint).toHaveBeenCalledOnce();

        ctx.closeRegistrationEditor();
        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(ctx.registrationEditor).toBeNull();
    });
});

vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));
vi.mock("./MainViewer.svelte", () => ({ default: {} }));
