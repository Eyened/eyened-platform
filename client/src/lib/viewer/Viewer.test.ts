import { fireEvent, render } from "@testing-library/svelte";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

import { viewerOf } from "./testViewer";
import Viewer from "./Viewer.svelte";

// jsdom has no pointer capture.
beforeAll(() => {
    Element.prototype.setPointerCapture ??= () => {};
    Element.prototype.releasePointerCapture ??= () => {};
});

describe("Viewer", () => {
    it.each(["popover-content", "tag-popover"])(
        "gives a press that closes an open %s to no tool",
        async (slot) => {
            const viewerContext = viewerOf("colour");
            const pointerdown = vi.fn();
            viewerContext.addOverlay({ pointerdown });
            const { container } = render(Viewer, {
                context: new Map<string, unknown>([
                    ["viewerContext", viewerContext],
                    ["viewerWindowContext", { addViewer: () => () => {} }],
                ]),
            });
            const viewport = container.querySelector<HTMLElement>(".viewer")!;
            const popover = document.body.appendChild(
                document.createElement("div"),
            );
            popover.dataset.slot = slot;
            await fireEvent.pointerDown(viewport, { pointerId: 1 });
            await fireEvent.pointerUp(viewport, { pointerId: 1 });
            expect(pointerdown).not.toHaveBeenCalled();
            popover.remove();
            await fireEvent.pointerDown(viewport, { pointerId: 1 });
            expect(pointerdown).toHaveBeenCalledOnce();
        },
    );

    it("a closing press released outside the viewer does not swallow the next release", async () => {
        const viewerContext = viewerOf("colour");
        const pointerup = vi.fn();
        viewerContext.addOverlay({ pointerdown: vi.fn(), pointerup });
        const { container } = render(Viewer, {
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer: () => () => {} }],
            ]),
        });
        const viewport = container.querySelector<HTMLElement>(".viewer")!;
        const popover = document.body.appendChild(
            document.createElement("div"),
        );
        popover.dataset.slot = "popover-content";
        await fireEvent.pointerDown(viewport, { pointerId: 1 });
        // The release lands outside the viewer, so no pointerup fires here.
        popover.remove();
        await fireEvent.pointerDown(viewport, { pointerId: 1 });
        await fireEvent.pointerUp(viewport, { pointerId: 1 });
        expect(pointerup).toHaveBeenCalledOnce();
    });
});
