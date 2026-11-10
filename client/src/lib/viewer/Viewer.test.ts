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
    it("gives a press that closes an open popover to no tool", async () => {
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
        popover.dataset.slot = "popover-content";
        await fireEvent.pointerDown(viewport, { pointerId: 1 });
        await fireEvent.pointerUp(viewport, { pointerId: 1 });
        expect(pointerdown).not.toHaveBeenCalled();
        popover.remove();
        await fireEvent.pointerDown(viewport, { pointerId: 1 });
        expect(pointerdown).toHaveBeenCalledOnce();
    });
});
