import { fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { viewerOf } from "$lib/viewer/testViewer";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import MagnifierPanel from "./MagnifierPanel.svelte";
import { expectNoAxeViolations, workspaceWith } from "./testUtils";
import type { Workspace } from "./workspace.svelte";
import { readMagnifier } from "./workspacePrefs";

// Counts image renderers: each one compiles four shader programs.
const renderers = vi.hoisted(() => ({ built: 0 }));
vi.mock("$lib/webgl/imageRenderer", () => ({
    BaseImageRenderer: class {
        constructor() {
            renderers.built++;
        }
    },
}));
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

afterEach(() => localStorage.clear());

function renderPanel(ws: Workspace, width = 1000, height = 700) {
    return render(MagnifierPanel, {
        props: { width, height, titleFor: () => null },
        context: new Map<string, unknown>([
            ["workspace", ws],
            ["viewerWindowContext", { addViewer: () => () => {} }],
        ]),
    });
}

const region = () => screen.queryByRole("region", { name: "Magnifier" });

// jsdom lays out nothing, so the panel measures 0 × 0 and the corners sit on the insets.
// The strip is on: bottom-left is 16 px from the left, 40 px from the bottom; the top corners are 104 + 32 px from the top.
describe("MagnifierPanel", () => {
    it("shows only while on, with no view until the pointer has been over a viewport; ✕ turns it off", async () => {
        const ws = workspaceWith(1);
        const { container } = renderPanel(ws);
        expect(region()).toBeNull();
        ws.setMagnifier({ on: true });
        await tick();
        expect(region()).toBeInTheDocument();
        expect(container.querySelector(".viewer")).toBeNull();
        await expectNoAxeViolations(container);
        await fireEvent.click(
            screen.getByRole("button", { name: "Close magnifier" }),
        );
        expect(ws.magnifier.on).toBe(false);
        expect(readMagnifier().on).toBe(false);
        expect(region()).toBeNull();
    });

    it("starts bottom-left; a gripper click stores the next corner; after a drag a click goes back to the start", async () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true });
        renderPanel(ws);
        expect(region()).toHaveStyle({ left: "16px", top: "660px" });
        const gripper = screen.getByRole("button", {
            name: "Move magnifier to next corner",
        });
        await fireEvent.click(gripper);
        expect(readMagnifier()).toMatchObject({ corner: 1, x: null, y: null });
        expect(region()).toHaveStyle({ left: "16px", top: "136px" });

        await fireEvent.pointerDown(gripper, {
            button: 0,
            clientX: 500,
            clientY: 500,
        });
        await fireEvent.pointerMove(gripper, { clientX: 560, clientY: 470 });
        await fireEvent.pointerUp(gripper);
        await fireEvent.click(gripper);
        expect(readMagnifier()).toMatchObject({ x: 76, y: 106 });

        await fireEvent.click(gripper);
        expect(readMagnifier()).toMatchObject({ corner: 0, x: null, y: null });
        expect(region()).toHaveStyle({ left: "16px", top: "660px" });
    });

    it("a corner stays a corner, with its inset, in a smaller workspace", async () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true });
        const { rerender } = renderPanel(ws);
        const gripper = screen.getByRole("button", {
            name: "Move magnifier to next corner",
        });
        for (let i = 0; i < 3; i++) await fireEvent.click(gripper);
        expect(region()).toHaveStyle({ left: "984px", top: "660px" });
        await rerender({ width: 400, height: 300 });
        expect(region()).toHaveStyle({ left: "384px", top: "260px" });
    });

    it("a cancelled drag drops the move: the panel stays at its stored place", async () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true, x: 924, y: 630 });
        renderPanel(ws);
        const gripper = screen.getByRole("button", {
            name: "Move magnifier to next corner",
        });
        await fireEvent.pointerDown(gripper, {
            button: 0,
            clientX: 500,
            clientY: 500,
        });
        await fireEvent.pointerMove(gripper, { clientX: 440, clientY: 470 });
        await fireEvent.pointerCancel(gripper);
        await fireEvent.pointerMove(gripper, { clientX: 300, clientY: 300 });
        expect(region()).toHaveStyle({ left: "924px", top: "630px" });
        expect(readMagnifier()).toMatchObject({ x: 924, y: 630 });
    });

    it("shows a stored place clamped inside a smaller workspace and keeps it stored", () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true, x: 900, y: 600 });
        renderPanel(ws, 400, 300);
        expect(region()).toHaveStyle({ left: "400px", top: "300px" });
        expect(ws.magnifier).toMatchObject({ x: 900, y: 600 });
    });

    it("Zoom and Size write their setting; the view takes the size", async () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true });
        const { container } = renderPanel(ws);
        await fireEvent.click(screen.getByRole("radio", { name: "6×" }));
        await fireEvent.click(screen.getByRole("radio", { name: "Large" }));
        expect(readMagnifier()).toMatchObject({ zoom: 6, size: "large" });
        expect(container.querySelector(".view")).toHaveStyle({
            width: "340px",
            height: "340px",
        });
    });

    it("shows the source viewport, dimmed once the pointer has left it", async () => {
        const ws = workspaceWith(1);
        ws.setMagnifier({ on: true });
        const { container } = renderPanel(ws);
        ws.magnifierSource = {
            viewerContext: viewerOf("colour", { workspace: ws }),
            mainViewerContext: { repaint() {} } as unknown as MainViewerContext,
            position: 0,
            x: 10,
            y: 10,
            inside: false,
        };
        await tick();
        expect(container.querySelector(".viewer")).not.toBeNull();
        expect(container.querySelector(".view")).toHaveClass("dimmed");
        expect(region()).toHaveTextContent("Viewport 1");
    });

    it("builds one view per source viewport: going back to a viewport builds no new renderer", async () => {
        const ws = workspaceWith(2);
        ws.setMagnifier({ on: true });
        renderPanel(ws);
        const a = viewerOf("colour", { workspace: ws, imageId: "a" });
        const b = viewerOf("grey", { workspace: ws, imageId: "b" });
        const over = (viewerContext: ViewerContext) => {
            ws.magnifierSource = {
                viewerContext,
                mainViewerContext: {
                    repaint() {},
                } as unknown as MainViewerContext,
                position: 0,
                x: 10,
                y: 10,
                inside: true,
            };
            return tick();
        };
        const before = renderers.built;
        await over(a);
        await over(b);
        await over(a);
        expect(renderers.built - before).toBe(2);
    });
});
