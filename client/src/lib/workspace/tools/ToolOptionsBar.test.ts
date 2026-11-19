import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "../testUtils";
import type { DrawTarget } from "$lib/layers/drawBinding";
import type { Workspace } from "../workspace.svelte";
import ToolOptionsBar from "./ToolOptionsBar.svelte";

const EDITABLE: DrawTarget = {
    name: { segmentation: "AMD grading", feature: "Drusen" },
    reason: null,
};

function drawViewport(ws: Workspace, drawTarget: DrawTarget) {
    const segmentationContext = {
        canUndo: () => false,
        canRedo: () => false,
        undo: vi.fn(),
        redo: vi.fn(),
    };
    ws.attachViewport(0, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            drawTarget,
            viewerContext: {
                image: { is2D: true },
                index: 0,
                returnFocus: vi.fn(),
            },
            mainViewerContext: { segmentationContext },
        } as never,
    });
    return segmentationContext;
}

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

    it("names the selected viewport's target; Undo at an empty history keeps focus", async () => {
        const ws = workspaceWith(1);
        const segmentation = drawViewport(ws, EDITABLE);
        ws.arm("brush");
        const { container } = render(ToolOptionsBar, {
            context: workspaceContext(ws),
        });
        expect(screen.getByText("AMD grading")).toBeInTheDocument();
        expect(screen.getByText("Drusen")).toBeInTheDocument();
        const undo = screen.getByRole("button", { name: "Undo" });
        expect(screen.getByRole("group", { name: "History" })).toContainElement(
            undo,
        );
        expect(undo).toHaveAttribute("aria-disabled", "true");
        undo.focus();
        await fireEvent.click(undo);
        expect(undo).toHaveFocus();
        expect(segmentation.undo).not.toHaveBeenCalled();
        await expectNoAxeViolations(container);
    });

    it("says in the status why it can't draw, in place of the options", () => {
        const other = workspaceWith(1);
        drawViewport(other, {
            name: { segmentation: "Vessels", feature: null },
            reason: "Another grader's segmentation can't be edited. Duplicate it to edit.",
        });
        other.arm("brush");
        render(ToolOptionsBar, { context: workspaceContext(other) });
        expect(screen.getByRole("status")).toHaveTextContent(
            "Another grader's segmentation can't be edited. Duplicate it to edit.",
        );
        expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
    });
});

describe("ToolOptionsBar when short", () => {
    afterEach(() => vi.restoreAllMocks());

    /** The options in the bar's row (History's included), not those in More. */
    function rowOptions(bar: Element) {
        return [...bar.querySelectorAll("[data-option]")].filter(
            (el) => !el.closest("[data-slot=overflow-menu]"),
        );
    }

    // jsdom has no layout: the bar is `px` wide and each option in its row takes 100 px.
    function barWidth(px: number) {
        const isBar = (el: Element) => el.matches("[data-slot=tool-options]");
        vi.spyOn(Element.prototype, "clientWidth", "get").mockImplementation(
            function (this: Element) {
                return isBar(this) ? px : 0;
            },
        );
        vi.spyOn(Element.prototype, "scrollWidth", "get").mockImplementation(
            function (this: Element) {
                return isBar(this) ? rowOptions(this).length * 100 : 0;
            },
        );
    }

    function inRow(container: Element) {
        const bar = container.querySelector("[data-slot=tool-options]")!;
        return rowOptions(bar).map((el) => el.getAttribute("data-option"));
    }

    function renderBrush(px: number, target: DrawTarget = EDITABLE) {
        barWidth(px);
        const ws = workspaceWith(1);
        drawViewport(ws, target);
        ws.arm("brush");
        return render(ToolOptionsBar, { context: workspaceContext(ws) });
    }

    it("folds Redo, then Undo, then settings from the right into More, Size last", async () => {
        const { container } = renderBrush(350);
        await vi.waitFor(() =>
            expect(inRow(container)).toEqual([
                "size",
                "dilateErode",
                "questionable",
            ]),
        );
        const menu = container.querySelector<HTMLElement>(
            "[data-slot=overflow-menu]",
        )!;
        for (const name of ["Undo", "Redo"])
            expect(
                within(menu).getByRole("button", { name, hidden: true }),
            ).toBeInTheDocument();
        cleanup();
        vi.restoreAllMocks();
        const narrow = renderBrush(150);
        await vi.waitFor(() =>
            expect(inRow(narrow.container)).toEqual(["size"]),
        );
    });

    it("never folds a can't-edit reason", async () => {
        renderBrush(50, {
            name: null,
            reason: "No current segmentation. Choose one in Segmentations.",
        });
        await tick();
        expect(screen.getByRole("status")).toHaveTextContent(
            "No current segmentation. Choose one in Segmentations.",
        );
        expect(screen.queryByRole("button", { name: "More" })).toBeNull();
    });
});
