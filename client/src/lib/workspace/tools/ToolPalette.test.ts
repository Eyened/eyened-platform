import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "../testUtils";
import type { Workspace } from "../workspace.svelte";
import ToolPalette from "./ToolPalette.svelte";

// All tools: 12 slots and 3 gaps between the 4 jobs.
const ALL_TOOLS_FLAT = 12 * 40 + 3 * 12;

function renderPalette(ws: Workspace, available: number) {
    return render(ToolPalette, {
        props: { available },
        context: workspaceContext(ws),
    });
}

describe("ToolPalette", () => {
    it("is flat while every slot fits; a pixel short, each job is a split slot", async () => {
        const ws = workspaceWith(1);
        const flat = renderPalette(ws, ALL_TOOLS_FLAT);
        expect(
            screen.getByRole("toolbar", { name: "Tools" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Eraser" }),
        ).toBeInTheDocument();
        flat.unmount();

        renderPalette(ws, ALL_TOOLS_FLAT - 1);
        expect(screen.queryByRole("button", { name: "Eraser" })).toBeNull();
        expect(
            screen.getByRole("button", { name: "Reset view" }),
        ).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("button", { name: "Brush" }));
        expect(ws.armedTool).toBe("brush");
        await fireEvent.click(
            screen.getByRole("button", { name: "Draw tools" }),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Eraser" }));
        expect(ws.armedTool).toBe("eraser");
        expect(
            screen.getByRole("button", { name: "Eraser" }),
        ).toBeInTheDocument();
    });

    it("split layout has one tab stop; ArrowDown moves from the View tool to its chevron", async () => {
        renderPalette(workspaceWith(1), ALL_TOOLS_FLAT - 1);
        const stops = screen
            .getAllByRole("button")
            .filter((b) => b.getAttribute("tabindex") === "0");
        expect(stops).toHaveLength(1);
        stops[0].focus();
        await fireEvent.keyDown(stops[0], { key: "ArrowDown" });
        expect(
            screen.getByRole("button", { name: "View tools" }),
        ).toHaveFocus();
    });

    it("a long press on a split slot opens its list and leaves the armed tool alone", async () => {
        vi.useFakeTimers();
        try {
            const ws = workspaceWith(1);
            ws.arm("brush");
            renderPalette(ws, ALL_TOOLS_FLAT - 1);
            const brush = screen.getByRole("button", { name: "Brush" });
            await fireEvent.pointerDown(brush, { button: 0 });
            await vi.advanceTimersByTimeAsync(500);
            await fireEvent.pointerUp(brush);
            await fireEvent.click(brush, { detail: 1 });
            expect(
                screen.getByRole("button", { name: "Polygon" }),
            ).toBeInTheDocument();
            expect(ws.armedTool).toBe("brush");
        } finally {
            vi.useRealTimers();
        }
    });

    it("a long press released off the button does not swallow a later key click", async () => {
        vi.useFakeTimers();
        try {
            const ws = workspaceWith(1);
            ws.arm("brush");
            renderPalette(ws, ALL_TOOLS_FLAT - 1);
            const brush = screen.getByRole("button", { name: "Brush" });
            await fireEvent.pointerDown(brush, { button: 0 });
            await vi.advanceTimersByTimeAsync(500);
            await fireEvent.click(brush, { detail: 0 });
            expect(ws.armedTool).toBeNull();
        } finally {
            vi.useRealTimers();
        }
    });

    it("presses the armed tool, and a second click returns to No tool", async () => {
        const ws = workspaceWith(1);
        renderPalette(ws, 1000);
        const zoom = screen.getByRole("button", { name: "Zoom" });
        await fireEvent.click(zoom);
        expect(zoom).toHaveAttribute("aria-pressed", "true");
        await fireEvent.click(zoom);
        expect(ws.armedTool).toBeNull();
        expect(zoom).toHaveAttribute("aria-pressed", "false");
    });

    it("in Browse, ⋯ lists the left-out tools by job and shows the one armed from it", async () => {
        const ws = workspaceWith(1);
        ws.toolMode = "browse";
        const { container } = renderPalette(ws, 1000);
        expect(screen.queryByRole("button", { name: "Brush" })).toBeNull();
        expect(
            screen.getByRole("button", { name: "Distance" }),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "More tools" }),
        );
        expect(screen.getByText("Draw")).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("button", { name: "Brush" }));
        expect(ws.armedTool).toBe("brush");
        expect(
            screen.getByRole("button", { name: "Brush (More tools)" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });
});
