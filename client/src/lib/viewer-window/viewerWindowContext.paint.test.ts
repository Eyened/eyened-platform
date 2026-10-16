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
        vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
        vi.stubGlobal("cancelAnimationFrame", vi.fn());
    });

    afterEach(() => {
        ctx?.destroy();
        ctx = undefined;
        vi.unstubAllGlobals();
    });

    it("paints only viewers added during the session, then resumes the others", () => {
        const background = { repaint: vi.fn() };
        const editorViewer = { repaint: vi.fn() };
        ctx = createContext();
        ctx.addViewer(background as never);

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
