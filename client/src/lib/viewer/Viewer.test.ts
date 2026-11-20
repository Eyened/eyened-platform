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
import type { ViewerEvent } from "./viewer-utils";

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

    it("sends the keyboard cursor's clicks to the tools at the cursor, with no modifiers", async () => {
        const viewerContext = viewerOf("colour");
        const events: {
            name: string;
            x: number;
            y: number;
            shift: boolean;
            button: number;
        }[] = [];
        const spy = (name: string) => (e: ViewerEvent<PointerEvent>) =>
            events.push({
                name,
                x: e.cursor.x,
                y: e.cursor.y,
                shift: e.modifiers.shift,
                button: e.event.button,
            });
        const keydown = vi.fn();
        viewerContext.addOverlay({
            pointerdown: spy("pointerdown"),
            pointermove: spy("pointermove"),
            pointerup: spy("pointerup"),
            keydown,
        });
        const { container } = render(Viewer, {
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer: () => () => {} }],
            ]),
        });
        const viewport = container.querySelector<HTMLElement>(".viewer")!;
        viewport.focus();
        await fireEvent.keyDown(viewport, { key: "Enter", code: "Enter" });
        await fireEvent.keyDown(viewport, {
            key: "Shift",
            code: "ShiftLeft",
            shiftKey: true,
        });
        await fireEvent.keyDown(viewport, {
            key: "ArrowRight",
            code: "ArrowRight",
            shiftKey: true,
        });
        await fireEvent.keyUp(viewport, { key: "Shift", code: "ShiftLeft" });
        for (let i = 0; i < 3; i++)
            await fireEvent.keyDown(viewport, {
                key: "ArrowRight",
                code: "ArrowRight",
            });
        await fireEvent.keyDown(viewport, { key: " ", code: "Space" });
        await fireEvent.keyUp(viewport, { key: " ", code: "Space" });
        expect(events.at(0)).toEqual({
            name: "pointermove",
            x: 50,
            y: 50,
            shift: false,
            button: -1,
        });
        expect(events.at(1)).toEqual({
            name: "pointermove",
            x: 60,
            y: 50,
            shift: false,
            button: -1,
        });
        expect(events.slice(-2)).toEqual([
            { name: "pointerdown", x: 63, y: 50, shift: false, button: 0 },
            { name: "pointerup", x: 63, y: 50, shift: false, button: 0 },
        ]);
        expect(viewerContext.active).toBe(true);
        // The cursor took Enter, the arrows and Space; tools only saw Shift.
        expect(keydown.mock.calls.map(([e]) => e.event.key)).toEqual(["Shift"]);
        expect(container.querySelector('[role="status"]')).toHaveTextContent(
            "Keyboard cursor on",
        );
    });

    it("blur ends the keyboard cursor and releases a held press", async () => {
        const viewerContext = viewerOf("colour");
        const pointerup = vi.fn();
        viewerContext.addOverlay({ pointerup });
        const { container } = render(Viewer, {
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer: () => () => {} }],
            ]),
        });
        const viewport = container.querySelector<HTMLElement>(".viewer")!;
        viewport.focus();
        await fireEvent.keyDown(viewport, { key: "Enter", code: "Enter" });
        await fireEvent.keyDown(viewport, { key: " ", code: "Space" });
        await fireEvent.blur(viewport);
        expect(pointerup).toHaveBeenCalledOnce();
        expect(viewerContext.keyboardCursor.on).toBe(false);
        expect(viewerContext.active).toBe(false);
        expect(container.querySelector('[role="status"]')).toHaveTextContent(
            "Keyboard cursor off",
        );
    });
});
