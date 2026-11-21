import { fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

import { Line } from "$lib/layers/distanceLines.svelte";
import { viewerOf } from "$lib/viewer/testViewer";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import Viewer from "$lib/viewer/Viewer.svelte";
import { readPaint } from "../workspacePrefs";
import { Workspace } from "../workspace.svelte";
import { Keymap } from "./keymap";

type ViewerCtx = ReturnType<typeof viewerOf>;

function press(
    viewer: ViewerCtx,
    init: Partial<KeyboardEvent>,
    type: "keydown" | "keyup" = "keydown",
): void {
    new Keymap()[type]({
        event: {
            key: "",
            code: "",
            repeat: false,
            ctrlKey: false,
            metaKey: false,
            altKey: false,
            shiftKey: false,
            preventDefault: () => {},
            ...init,
        },
        viewerContext: viewer,
    } as unknown as ViewerEvent<KeyboardEvent>);
}

function attachSelected(
    workspace: Workspace,
    viewer: ViewerCtx,
    isDrawing = false,
    regionToolActive = false,
) {
    const segmentationContext = {
        isDrawing,
        regionToolActive,
        undo: vi.fn(),
        redo: vi.fn(),
    };
    workspace.attachViewport(0, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            viewerContext: viewer,
            mainViewerContext: { segmentationContext },
        } as never,
    });
    return segmentationContext;
}

describe("Keymap", () => {
    afterEach(() => localStorage.clear());

    it("the armed tool's key again returns to No tool", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        press(viewer, { key: "b", code: "KeyB" });
        expect(workspace.armedTool).toBe("brush");
        press(viewer, { key: "b", code: "KeyB" });
        expect(workspace.armedTool).toBeNull();
    });

    it("Esc cancels a waiting region box and keeps the view (#325)", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        const segmentation = attachSelected(workspace, viewer, false, true);
        const reset = vi.spyOn(viewer, "initTransform");
        press(viewer, { key: "Escape", code: "Escape" });
        expect(segmentation.regionToolActive).toBe(false);
        expect(reset).not.toHaveBeenCalled();
        press(viewer, { key: "Escape", code: "Escape" });
        expect(reset).toHaveBeenCalledOnce();
    });

    it("Esc leaves the keyboard cursor before it resets the view", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        viewer.keyboardCursor.host = {
            size: () => ({ width: 100, height: 100 }),
            send: () => {},
            changed: () => {},
        };
        viewer.keyboardCursor.keydown(
            new KeyboardEvent("keydown", { key: "Enter", code: "Enter" }),
        );
        const reset = vi.spyOn(viewer, "initTransform");
        press(viewer, { key: "Escape", code: "Escape" });
        expect(viewer.keyboardCursor.on).toBe(false);
        expect(reset).not.toHaveBeenCalled();
        press(viewer, { key: "Escape", code: "Escape" });
        expect(reset).toHaveBeenCalledOnce();
    });

    it("arms a tool by its letter only while a viewport has focus", async () => {
        const workspace = new Workspace();
        const viewerContext = viewerOf("colour", { workspace });
        const { container } = render(Viewer, {
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer: () => () => {} }],
            ]),
        });
        await fireEvent.keyDown(document.body, { key: "z", code: "KeyZ" });
        expect(workspace.armedTool).toBeNull();
        const viewport = container.querySelector<HTMLElement>(".viewer")!;
        viewport.focus();
        await fireEvent.keyDown(viewport, { key: "z", code: "KeyZ" });
        expect(workspace.armedTool).toBe("zoom");
    });

    it("ignores letters with Ctrl, Meta or Alt, and matches either case", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        press(viewer, { key: "z", ctrlKey: true });
        press(viewer, { key: "t", metaKey: true });
        press(viewer, { key: "j", altKey: true });
        expect(workspace.armedTool).toBeNull();
        press(viewer, { key: "T" });
        expect(workspace.armedTool).toBe("pan");
    });

    it("picks render presets by the digit's physical key, and skips a mode the image lacks", () => {
        const colour = viewerOf("colour");
        press(colour, { key: "é", code: "Digit2" });
        expect(colour.renderMode).toBe("Contrast enhanced");
        press(colour, { key: "à", code: "Digit0" });
        expect(colour.renderMode).toBe("Blue");
        press(colour, { key: "&", code: "Digit1" });
        expect(colour.renderMode).toBe("Original");
        const grey = viewerOf("grey");
        press(grey, { key: "2", code: "Digit2" });
        expect(grey.renderMode).toBe("Original");
        press(grey, { key: "4", code: "Digit4" });
        expect(grey.renderMode).toBe("CLAHE");
    });

    it("hides overlays while H is held; Space no longer does", () => {
        const viewer = viewerOf("colour");
        press(viewer, { key: " ", code: "Space" });
        expect(viewer.hideOverlays).toBe(false);
        press(viewer, { key: "h", code: "KeyH" });
        expect(viewer.hideOverlays).toBe(true);
        expect(viewer.renderMode).toBe("Original");
        press(viewer, { key: "h", code: "KeyH" }, "keyup");
        expect(viewer.hideOverlays).toBe(false);
    });

    it("shows overlays again when the viewport loses focus while H is held", async () => {
        const workspace = new Workspace();
        const viewerContext = viewerOf("colour", { workspace });
        const { container } = render(Viewer, {
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer: () => () => {} }],
            ]),
        });
        const viewport = container.querySelector<HTMLElement>(".viewer")!;
        viewport.focus();
        await fireEvent.keyDown(viewport, { key: "h", code: "KeyH" });
        expect(viewerContext.hideOverlays).toBe(true);
        await fireEvent.blur(viewport);
        expect(viewerContext.hideOverlays).toBe(false);
    });

    it("Esc fits zoom and pan again", () => {
        const viewer = viewerOf("colour");
        viewer.zoom(10, 10, 3);
        press(viewer, { key: "Escape", code: "Escape" });
        expect(viewer.transform).toEqual(viewer.getInitTransform());
    });

    it("Esc while a tooltip is open leaves the view for the tooltip to close", () => {
        const viewer = viewerOf("colour");
        viewer.zoom(10, 10, 3);
        const zoomed = { ...viewer.transform };
        const tooltip = document.createElement("div");
        tooltip.dataset.slot = "tooltip-content";
        tooltip.dataset.state = "delayed-open";
        document.body.append(tooltip);
        press(viewer, { key: "Escape", code: "Escape" });
        expect(viewer.transform).toEqual(zoomed);
        tooltip.remove();
        press(viewer, { key: "Escape", code: "Escape" });
        expect(viewer.transform).toEqual(viewer.getInitTransform());
    });

    it("Esc acts at once while only the viewport's title tooltip is open", () => {
        const viewer = viewerOf("colour");
        viewer.zoom(10, 10, 3);
        const title = document.createElement("div");
        title.dataset.slot = "tooltip-content";
        title.dataset.state = "delayed-open";
        title.dataset.viewportTitle = "";
        document.body.append(title);
        try {
            press(viewer, { key: "Escape", code: "Escape" });
            expect(viewer.transform).toEqual(viewer.getInitTransform());
        } finally {
            title.remove();
        }
    });

    it("Esc drops a half-drawn distance line first; the next Esc fits the view and clears the image's lines, not another image's or from a strip tile", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace, imageId: "a" });
        const tile = viewerOf("colour", {
            workspace,
            imageId: "a",
            tile: true,
        });
        const line = () => new Line({ x: 0, y: 0 }, { x: 1, y: 1 }, 0);
        const a = workspace.distanceLinesFor("a");
        a.add(line());
        const half = line();
        a.add(half);
        a.drawing = half;
        workspace.distanceLinesFor("b").add(line());
        viewer.zoom(10, 10, 3);
        press(viewer, { key: "Escape", code: "Escape" });
        expect(a.lines).toHaveLength(1);
        expect(viewer.transform).not.toEqual(viewer.getInitTransform());
        press(tile, { key: "Escape", code: "Escape" });
        expect(a.lines).toHaveLength(1);
        press(viewer, { key: "Escape", code: "Escape" });
        expect(a.lines).toHaveLength(0);
        expect(viewer.transform).toEqual(viewer.getInitTransform());
        expect(workspace.distanceLinesFor("b").lines).toHaveLength(1);
    });

    it("M shows and hides the Magnifier and keeps the armed tool; Esc leaves it on", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        workspace.arm("brush");
        press(viewer, { key: "m", code: "KeyM" });
        expect(workspace.magnifier.on).toBe(true);
        expect(workspace.armedTool).toBe("brush");
        press(viewer, { key: "Escape", code: "Escape" });
        expect(workspace.magnifier.on).toBe(true);
        press(viewer, { key: "M", code: "KeyM" });
        expect(workspace.magnifier.on).toBe(false);
    });

    it("Ctrl+Z and ⌘Z undo the selected viewport on its slice once per press, with any tool; Ctrl+Y and ⇧⌘Z redo", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("bscan", { workspace });
        const segmentation = attachSelected(workspace, viewer);
        workspace.arm("zoom");
        press(viewer, { key: "z", ctrlKey: true });
        press(viewer, { key: "z", metaKey: true });
        press(viewer, { key: "z", ctrlKey: true, repeat: true });
        expect(segmentation.undo.mock.calls).toEqual([
            [viewer.index],
            [viewer.index],
        ]);
        press(viewer, { key: "y", ctrlKey: true });
        press(viewer, { key: "Z", metaKey: true, shiftKey: true });
        expect(segmentation.redo).toHaveBeenCalledTimes(2);
        expect(workspace.armedTool).toBe("zoom");
    });

    it("X swaps Brush and Eraser, Fill and Erase, Increase and Decrease; during a stroke X, a tool letter, ] and ⌘Z do nothing", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        workspace.arm("brush");
        press(viewer, { key: "x" });
        expect(workspace.armedTool).toBe("eraser");
        press(viewer, { key: "X" });
        expect(workspace.armedTool).toBe("brush");
        workspace.arm("polygon");
        press(viewer, { key: "x" });
        expect(workspace.remove).toBe(true);
        workspace.arm("enhance");
        press(viewer, { key: "x" });
        expect(workspace.remove).toBe(false);

        workspace.arm("brush");
        const segmentation = attachSelected(workspace, viewer, true);
        press(viewer, { key: "x" });
        press(viewer, { key: "z" });
        press(viewer, { key: "]" });
        press(viewer, { key: "z", metaKey: true });
        expect(workspace.armedTool).toBe("brush");
        expect(workspace.paint.size2D).toBe(4);
        expect(segmentation.undo).not.toHaveBeenCalled();
    });

    it("] and [ step the brush size for this image's kind only, and store it", () => {
        const workspace = new Workspace();
        const fundus = viewerOf("colour", { workspace });
        const bscan = viewerOf("bscan", { workspace });
        workspace.arm("brush");
        press(fundus, { key: "]" });
        expect(workspace.paint).toMatchObject({ size2D: 5, sizeBscan: 4 });
        press(bscan, { key: "[" });
        expect(workspace.paint).toMatchObject({ size2D: 5, sizeBscan: 3.2 });
        expect(readPaint()).toMatchObject({ size2D: 5, sizeBscan: 3.2 });
    });

    it("] and [ step the ETDRS circle size and stop at the ends; with Place ETDRS they pick Disc edge and Fovea", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("colour", { workspace });
        workspace.arm("circle");
        for (let i = 0; i < 8; i++) press(viewer, { key: "]" });
        expect(workspace.circleSize).toBe("O2");
        press(viewer, { key: "[" });
        expect(workspace.circleSize).toBe("O1");
        workspace.arm("etdrs");
        press(viewer, { key: "]" });
        expect(workspace.etdrsSlot).toBe(1);
        press(viewer, { key: "[" });
        expect(workspace.etdrsSlot).toBe(0);
        expect(workspace.circleSize).toBe("O1");
    });
});
