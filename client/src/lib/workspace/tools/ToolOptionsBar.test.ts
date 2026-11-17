import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "../testUtils";
import ToolOptionsBar from "./ToolOptionsBar.svelte";

describe("ToolOptionsBar", () => {
    it("names Zoom, shows the selected viewport's zoom and steps it", async () => {
        const ws = workspaceWith(2);
        const zoomBy = vi.fn();
        ws.attachViewport(0, { zoomPercent: 150, zoomBy, reset: vi.fn() });
        ws.arm("zoom");
        const { container } = render(ToolOptionsBar, {
            context: workspaceContext(ws),
        });
        expect(screen.getByText("Zoom")).toBeInTheDocument();
        expect(screen.getByText("150%")).toBeInTheDocument();
        expect(
            screen.getByText("Drag down zooms in, up zooms out"),
        ).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
        expect(zoomBy).toHaveBeenLastCalledWith(1.25);
        await fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
        expect(zoomBy).toHaveBeenLastCalledWith(0.8);
        await expectNoAxeViolations(container);
    });

    it("names the registration P places into, read-only for a colleague's, or asks for one", () => {
        const show = (pointTarget: { id: number; canEdit: boolean } | null) => {
            const ws = workspaceWith(1);
            ws.attachViewport(0, {
                zoomPercent: 100,
                zoomBy: vi.fn(),
                reset: vi.fn(),
                layers: { pointTarget } as never,
            });
            ws.arm("point");
            return render(ToolOptionsBar, { context: workspaceContext(ws) });
        };
        show(null);
        expect(
            screen.getByText("Make a registration current in Pointsets."),
        ).toBeInTheDocument();
        cleanup();
        show({ id: 640, canEdit: false });
        expect(
            screen.getByText("Registration [640] · read-only"),
        ).toBeInTheDocument();
    });
});
