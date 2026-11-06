import { describe, expect, it, vi } from "vitest";
import { viewerOf } from "../testViewer";
import type { ViewerEvent } from "../viewer-utils";
import { HotKeys } from "./hotkeys";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

const press = (
    viewerContext: ReturnType<typeof viewerOf>,
    code: string,
): void =>
    new HotKeys().keydown({
        event: { code },
        viewerContext,
    } as unknown as ViewerEvent<KeyboardEvent>);

describe("HotKeys", () => {
    it("ignores the mode keys without render controls, but not Space", () => {
        const viewer = viewerOf("grey");
        viewer.renderControls = false;
        press(viewer, "KeyH");
        expect(viewer.renderMode).toBe("Original");
        press(viewer, "Space");
        expect(viewer.hideOverlays).toBe(true);
    });
});
