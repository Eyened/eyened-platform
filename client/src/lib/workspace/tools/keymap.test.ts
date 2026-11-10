import { fireEvent, render } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

import { viewerOf } from "$lib/viewer/testViewer";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import Viewer from "$lib/viewer/Viewer.svelte";
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
            ...init,
        },
        viewerContext: viewer,
    } as unknown as ViewerEvent<KeyboardEvent>);
}

describe("Keymap", () => {
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

    it("Esc fits zoom and pan again", () => {
        const viewer = viewerOf("colour");
        viewer.zoom(10, 10, 3);
        press(viewer, { key: "Escape", code: "Escape" });
        expect(viewer.transform).toEqual(viewer.getInitTransform());
    });
});
