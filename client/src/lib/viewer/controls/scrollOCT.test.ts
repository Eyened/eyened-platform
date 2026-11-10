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
});
