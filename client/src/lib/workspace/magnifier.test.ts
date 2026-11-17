import { describe, expect, it, vi } from "vitest";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { viewerOf } from "$lib/viewer/testViewer";
import type { ViewerEvent } from "$lib/viewer/viewer-utils";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { clampInto, corners, magnifierFeed, nextCorner } from "./magnifier";
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

describe("magnifier place", () => {
    const area = { width: 1000, height: 700 };
    const panel = { width: 280, height: 360 };
    const inset = { top: 32, right: 16, bottom: 40, left: 16 };

    it("a gripper click visits top-right, bottom-right, bottom-left, top-left and round again; from a dragged place it goes to top-right", () => {
        const places = corners(area, panel, inset);
        expect(places).toEqual([
            { x: 704, y: 32 },
            { x: 704, y: 300 },
            { x: 16, y: 300 },
            { x: 16, y: 32 },
        ]);
        const seen = [];
        let p = places[0];
        for (let i = 0; i < 4; i++) {
            p = nextCorner(p, places);
            seen.push(p);
        }
        expect(seen).toEqual([places[1], places[2], places[3], places[0]]);
        expect(nextCorner({ x: 300, y: 200 }, places)).toEqual(places[0]);
    });

    it("shows a stored place inside a smaller workspace", () => {
        expect(
            clampInto({ x: 900, y: 600 }, { width: 600, height: 400 }, panel),
        ).toEqual({ x: 320, y: 40 });
        expect(clampInto({ x: -20, y: 10 }, area, panel)).toEqual({
            x: 0,
            y: 10,
        });
        expect(
            clampInto({ x: 50, y: 50 }, { width: 200, height: 200 }, panel),
        ).toEqual({ x: 0, y: 0 });
    });
});
