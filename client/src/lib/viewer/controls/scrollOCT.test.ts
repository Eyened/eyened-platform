import { describe, expect, it, vi } from "vitest";
import { Workspace } from "$lib/workspace/workspace.svelte";
import { viewerOf } from "../testViewer";
import type { ViewerEvent } from "../viewer-utils";
import { ScrollOCT } from "./scrollOCT";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

describe("ScrollOCT", () => {
    it("does not scroll a locked B-scan", () => {
        const workspace = new Workspace();
        const viewer = viewerOf("bscan", { workspace });
        workspace.setLocked("img-bscan", true);
        new ScrollOCT().wheel({
            viewerContext: viewer,
            wheel: { zoomIntent: false, primaryDeltaPx: 100 },
        } as unknown as ViewerEvent<WheelEvent>);
        expect(viewer.index).toBe(64);
    });

    it("stops at the first and last slice instead of wrapping", () => {
        const viewer = viewerOf("bscan");
        const key = (code: string) =>
            new ScrollOCT().keydown({
                event: { code },
                viewerContext: viewer,
            } as unknown as ViewerEvent<KeyboardEvent>);
        viewer.index = 0;
        key("ArrowUp");
        expect(viewer.index).toBe(0);
        viewer.index = 127;
        key("ArrowDown");
        expect(viewer.index).toBe(127);
    });
});
