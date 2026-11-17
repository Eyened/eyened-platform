import { describe, expect, it, vi } from "vitest";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { viewerOf } from "$lib/viewer/testViewer";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { magnifierFeed } from "./magnifier";
import { Workspace } from "./workspace.svelte";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

const at = (viewerContext: ViewerContext, x: number, y: number) =>
    ({
        viewerContext,
        cursor: { x, y },
    }) as unknown as ViewerEvent<PointerEvent>;

describe("magnifierFeed", () => {
    it("follows the pointer in image coordinates, and dims only when it leaves the viewport it came from", () => {
        const workspace = new Workspace();
        const main = {} as MainViewerContext;
        // A 512 px square image fitted to 200 px, then zoomed 2× about the top-left: 400/512 screen px per image px.
        const a = viewerOf("colour", { workspace });
        a.viewerSize = { width: 200, height: 200 };
        a.initTransform();
        a.zoom(0, 0, 2);
        const b = viewerOf("grey", { workspace });
        const feedA = magnifierFeed(workspace, main, () => 0);
        const feedB = magnifierFeed(workspace, main, () => 1);

        feedA.pointermove!(at(a, 50, 80));
        expect(workspace.magnifierSource).toMatchObject({
            viewerContext: a,
            position: 0,
            inside: true,
        });
        expect(workspace.magnifierSource!.x).toBeCloseTo(64);
        expect(workspace.magnifierSource!.y).toBeCloseTo(102.4);

        feedB.pointerleave!(at(b, 0, 0));
        expect(workspace.magnifierSource!.inside).toBe(true);
        feedA.pointerleave!(at(a, 0, 0));
        expect(workspace.magnifierSource).toMatchObject({
            viewerContext: a,
            inside: false,
        });
    });
});
