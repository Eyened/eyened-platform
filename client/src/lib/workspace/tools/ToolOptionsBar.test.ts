import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "../testUtils";
import type { DrawTarget } from "$lib/layers/drawBinding";
import type { Workspace } from "../workspace.svelte";
import { DistanceLines, Line } from "$lib/layers/distanceLines.svelte";
import type { Scale } from "$lib/layers/imageScale";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ToolId } from "./registry";
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
                keyboardCursor: { on: false },
            },
            mainViewerContext: { segmentationContext },
        } as never,
    });
    return segmentationContext;
}

const STORED: Scale = {
    x: 11.2,
    y: 11.2,
    source: "stored",
    pick: { kind: "stored" },
};

/** Arms a tool with one selected viewport whose layers handle carries `layers`. */
function armWith(tool: ToolId, layers: object) {
    const ws = workspaceWith(1);
    ws.attachViewport(0, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            viewerContext: {
                image: { image_id: "inst-1", width: 100 },
                index: 0,
                viewerSize: { width: 100 },
                setIndex: vi.fn(),
                focusPoint: vi.fn(),
                returnFocus: vi.fn(),
                keyboardCursor: { on: false },
            },
            ...layers,
        } as never,
    });
    ws.arm(tool);
    return render(ToolOptionsBar, { context: workspaceContext(ws) });
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

    it("shows the keyboard cursor's keys in place of the tool's hint while it is on", () => {
        const ws = workspaceWith(1);
        ws.attachViewport(0, {
            zoomPercent: 100,
            zoomBy: vi.fn(),
            reset: vi.fn(),
            layers: {
                viewerContext: { keyboardCursor: { on: true } },
            } as never,
        });
        ws.arm("zoom");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        expect(
            screen.getByText(
                "Keyboard cursor · arrows move, Shift 10 px · Space clicks, hold to drag · Esc leaves",
            ),
        ).toBeInTheDocument();
        expect(
            screen.queryByText("Drag down zooms in, up zooms out"),
        ).toBeNull();
    });

    it("names the registration P places into, read-only for a colleague's, or asks for one", () => {
        const show = (pointTarget: { id: number; canEdit: boolean } | null) => {
            const ws = workspaceWith(1);
            ws.attachViewport(0, {
                zoomPercent: 100,
                zoomBy: vi.fn(),
                reset: vi.fn(),
                layers: {
                    pointTarget,
                    viewerContext: { keyboardCursor: { on: false } },
                } as never,
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
            screen.getByText("Registration 640 · read-only"),
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

    it("Distance and the ETDRS circle name the scale and its source; without one, Distance measures in px and the circle says why, keeping the scale button", () => {
        armWith("distance", { scale: STORED, distance: new DistanceLines() });
        expect(
            screen.getByRole("button", { name: /11\.20 µm\/px · stored/ }),
        ).toBeInTheDocument();
        cleanup();
        armWith("distance", { scale: null, distance: new DistanceLines() });
        expect(
            screen.getByRole("button", { name: /No scale · lengths in px/ }),
        ).toBeInTheDocument();
        cleanup();
        armWith("circle", { scale: null });
        expect(screen.getByRole("status")).toHaveTextContent(
            "Set the image resolution, or show a grid in ETDRS grids.",
        );
        expect(
            screen.getByRole("button", { name: /No scale/ }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("radio", { name: "C1" })).toBeNull();
    });

    it("Distance's Delete removes the current line and is off when there is none", async () => {
        const distance = new DistanceLines();
        distance.add(new Line({ x: 0, y: 0 }, { x: 1, y: 1 }, 0));
        distance.add(new Line({ x: 0, y: 0 }, { x: 2, y: 2 }, 0));
        armWith("distance", { scale: null, distance });
        const remove = screen.getByRole("button", { name: "Delete" });
        await fireEvent.click(remove);
        expect(distance.lines.map((l) => l.end.x)).toEqual([1]);
        expect(remove).toHaveAttribute("aria-disabled", "true");
        await fireEvent.click(remove);
        expect(distance.lines).toHaveLength(1);
    });

    it("Place ETDRS names the grid, or says why it can't write it in place of the options", () => {
        armWith("etdrs", {
            etdrsTarget: {
                name: "Your grid 7",
                reason: "This grid is on another image.",
            },
        });
        expect(screen.getByText("Your grid 7")).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(
            "This grid is on another image.",
        );
        expect(screen.queryByRole("radio", { name: "Fovea" })).toBeNull();
    });

    it("Point steps through the registration's points: Point – / 3, then Point 1 / 3", async () => {
        const tool = new PointTool({ sparse: true });
        tool.points = [{ x: 1, y: 1 }, null, { x: 3, y: 3 }];
        const { container } = armWith("point", {
            pointTarget: { id: 4, canEdit: true },
            pointTool: tool,
        });
        expect(screen.getByText("Registration 4")).toBeInTheDocument();
        expect(screen.getByText("Point – / 3")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Next point" }),
        );
        expect(screen.getByText("Point 1 / 3")).toBeInTheDocument();
        await expectNoAxeViolations(container);
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

    it("the scale and Fovea | Disc edge never fold: Place ETDRS folds Delete, then Keep grid size; the circle folds its sizes", async () => {
        const renderTool = (px: number, tool: ToolId, layers: object) => {
            barWidth(px);
            const ws = workspaceWith(1);
            ws.attachViewport(0, {
                zoomPercent: 100,
                zoomBy: vi.fn(),
                reset: vi.fn(),
                layers: {
                    viewerContext: { keyboardCursor: { on: false } },
                    ...layers,
                } as never,
            });
            ws.arm(tool);
            return render(ToolOptionsBar, { context: workspaceContext(ws) });
        };
        const etdrs = { etdrsTarget: { name: "Your grid 12", reason: null } };
        const wide = renderTool(250, "etdrs", etdrs);
        await vi.waitFor(() =>
            expect(inRow(wide.container)).toEqual([
                "etdrsSlot",
                "keepGridSize",
            ]),
        );
        cleanup();
        vi.restoreAllMocks();
        const narrow = renderTool(50, "etdrs", etdrs);
        await vi.waitFor(() =>
            expect(inRow(narrow.container)).toEqual(["etdrsSlot"]),
        );
        cleanup();
        vi.restoreAllMocks();
        const circle = renderTool(150, "circle", { scale: STORED });
        await vi.waitFor(() =>
            expect(inRow(circle.container)).toEqual(["scale"]),
        );
    });
});
