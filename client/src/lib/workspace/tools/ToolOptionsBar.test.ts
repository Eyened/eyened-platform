import type { PointTarget } from "$lib/layers/pointsets";
import { pointArming } from "$lib/forms/pointArming.svelte";
import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    mockWidth,
    workspaceContext,
    workspaceWith,
} from "../testUtils";
import type { DrawTarget } from "$lib/layers/drawBinding";
import type { Workspace } from "../workspace.svelte";
import { DistanceLines, Line } from "$lib/layers/distanceLines.svelte";
import { LayerSelection } from "$lib/layers/layerSelection.svelte";
import type { Scale } from "$lib/layers/imageScale";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ToolId } from "./registry";
import ToolOptionsBar from "./ToolOptionsBar.svelte";

const EDITABLE: DrawTarget = {
    name: { segmentation: "AMD grading", feature: "Drusen" },
    color: null,
    reason: null,
};

function drawViewport(ws: Workspace, drawTarget: DrawTarget, cursor = false) {
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
                keyboardCursor: { on: cursor },
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
            selection: new LayerSelection(),
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
        await fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
        expect(zoomBy).toHaveBeenLastCalledWith(1.25);
        await fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
        expect(zoomBy).toHaveBeenLastCalledWith(0.8);
        await expectNoAxeViolations(container);
    });

    it("shows the keyboard cursor's keys after the tool while it is on", () => {
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
            screen.getByText("arrows move · Space clicks · Esc leaves"),
        ).toBeInTheDocument();
    });

    it("with no tool armed says so; Keys lists the keys that work without a tool and leaves focus on Keys", async () => {
        render(ToolOptionsBar, { context: workspaceContext(workspaceWith(1)) });
        expect(
            screen.getByText("No tool armed · pick one in Tools"),
        ).toBeInTheDocument();
        const keys = screen.getByRole("button", { name: "Keys" });
        keys.focus();
        await fireEvent.click(keys);
        const dialog = await screen.findByRole("dialog", { name: "Keys" });
        expect(
            within(dialog)
                .getAllByRole("heading")
                .map((h) => h.textContent?.trim()),
        ).toEqual(["Without a tool"]);
        expect(within(dialog).getByText("Localizer lines")).toBeInTheDocument();
        expect(keys).toHaveFocus();
    });

    it("with the keyboard cursor on and Brush armed, Keys lists the cursor's keys first", async () => {
        const ws = workspaceWith(1);
        drawViewport(ws, EDITABLE, true);
        ws.arm("brush");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        await fireEvent.click(screen.getByRole("button", { name: "Keys" }));
        const dialog = await screen.findByRole("dialog", { name: "Keys" });
        expect(
            within(dialog)
                .getAllByRole("heading")
                .map((h) => h.textContent?.trim()),
        ).toEqual(["Keyboard cursor", "Without a tool"]);
        expect(within(dialog).getByText("Leave")).toBeInTheDocument();
    });

    it("names the registration P places into, read-only for a colleague's, or asks for one", () => {
        const show = (pointTarget: PointTarget) => {
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
        show({
            id: null,
            canEdit: false,
            reason: "Select a pointset to add points",
        });
        expect(screen.getByRole("status")).toHaveTextContent(
            "Select a pointset to add points",
        );
        cleanup();
        show({ id: 640, canEdit: false, reason: null });
        expect(
            screen.getByText("Registration 640 · read-only"),
        ).toBeInTheDocument();
    });

    it("on a read-only pointset Keys lists only the previous / next point keys", async () => {
        const ws = workspaceWith(1);
        ws.attachViewport(0, {
            zoomPercent: 100,
            zoomBy: vi.fn(),
            reset: vi.fn(),
            layers: {
                pointTarget: { id: 640, canEdit: false, reason: null },
                viewerContext: { keyboardCursor: { on: false } },
            } as never,
        });
        ws.arm("point");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        await fireEvent.click(screen.getByRole("button", { name: "Keys" }));
        const dialog = await screen.findByRole("dialog", { name: "Keys" });
        const pointTable = within(dialog).getByRole("table", { name: "Point" });
        expect(
            within(pointTable)
                .getAllByRole("row")
                .slice(1)
                .map((r) =>
                    within(r)
                        .getAllByRole("cell")
                        .map((c) => c.textContent?.trim()),
                ),
        ).toEqual([["[ / ]", "Previous / next point"]]);
    });

    it("keeps Point's reason it can't act visible while the keyboard cursor is on", () => {
        const ws = workspaceWith(1);
        ws.attachViewport(0, {
            zoomPercent: 100,
            zoomBy: vi.fn(),
            reset: vi.fn(),
            layers: {
                pointTarget: {
                    id: null,
                    canEdit: false,
                    reason: "Select a pointset to add points",
                },
                viewerContext: { keyboardCursor: { on: true } },
            } as never,
        });
        ws.arm("point");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        expect(screen.getByRole("status")).toHaveTextContent(
            "Select a pointset to add points",
        );
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

    it("can't edit: a model segmentation's target stays and the reason replaces the options", () => {
        const ws = workspaceWith(1);
        drawViewport(ws, {
            name: { segmentation: "Vessels", feature: null },
            color: "#e5c07b",
            reason: "This model segmentation can't be edited. Duplicate it to edit.",
        });
        ws.arm("brush");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        expect(screen.getByText("Vessels")).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(
            "This model segmentation can't be edited. Duplicate it to edit.",
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

    it("Distance's Delete removes the selected line and is off when there is none", async () => {
        const distance = new DistanceLines();
        const line = new Line({ x: 0, y: 0 }, { x: 3, y: 4 }, 0);
        distance.add(line);
        distance.add(new Line({ x: 0, y: 0 }, { x: 6, y: 8 }, 0));
        const selection = new LayerSelection();
        selection.select({ kind: "line", line, lines: distance });
        armWith("distance", { distance, selection, scale: null });
        const remove = screen.getByRole("button", { name: "Delete" });
        await fireEvent.click(remove);
        expect(distance.lines.map((l) => l.end.x)).toEqual([6]);
        expect(remove).toHaveAttribute("aria-disabled", "true");
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

    it("Place ETDRS and the circle set the radius fraction on commit; it stays beside Place ETDRS's reason", async () => {
        const { unmount } = armWith("etdrs", {
            etdrsTarget: { name: "Your grid 7", reason: null },
        });
        const field = screen.getByLabelText("Radius fraction");
        await fireEvent.input(field, { target: { value: "0.9" } });
        await fireEvent.change(field);
        expect(field).toHaveValue(0.9);
        for (const bad of ["", "1.5"]) {
            await fireEvent.input(field, { target: { value: bad } });
            await fireEvent.keyDown(field, { key: "Enter" });
            expect(field).toHaveValue(0.9);
        }
        unmount();

        armWith("etdrs", {
            etdrsTarget: {
                name: "Your grid 7",
                reason: "This grid is on another image.",
            },
        });
        expect(screen.getByLabelText("Radius fraction")).toBeInTheDocument();
        expect(screen.queryByRole("radio", { name: "Fovea" })).toBeNull();
        cleanup();

        armWith("circle", { scale: STORED });
        expect(screen.getByLabelText("Radius fraction")).toBeInTheDocument();
    });

    it("Point steps through the registration's points: Point – / 3, then Point 1 / 3", async () => {
        const tool = new PointTool({ sparse: true });
        tool.points = [{ x: 1, y: 1 }, null, { x: 3, y: 3 }];
        const { container } = armWith("point", {
            pointTarget: { id: 4, canEdit: true, reason: null },
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

    it("Dilate / Erode, Questionable and Keep grid size are checkboxes that turn the option on", async () => {
        const ws = workspaceWith(1);
        drawViewport(ws, EDITABLE);
        ws.arm("brush");
        render(ToolOptionsBar, { context: workspaceContext(ws) });
        await fireEvent.click(
            screen.getByRole("checkbox", { name: "Dilate / Erode" }),
        );
        await fireEvent.click(
            screen.getByRole("checkbox", { name: "Questionable" }),
        );
        expect([ws.dilateErode, ws.questionable]).toEqual([true, true]);
        cleanup();

        const grid = workspaceWith(1);
        grid.attachViewport(0, {
            zoomPercent: 100,
            zoomBy: vi.fn(),
            reset: vi.fn(),
            layers: {
                etdrsTarget: { name: "Your grid 7", reason: null },
                viewerContext: {
                    keyboardCursor: { on: false },
                    returnFocus: vi.fn(),
                },
            } as never,
        });
        grid.arm("etdrs");
        render(ToolOptionsBar, { context: workspaceContext(grid) });
        const before = grid.keepGridSize;
        await fireEvent.click(
            screen.getByRole("checkbox", { name: "Keep grid size" }),
        );
        expect(grid.keepGridSize).toBe(!before);
    });
});

describe("ToolOptionsBar when short", () => {
    // Wide, as in the app: below 42rem the bar wraps instead of folding.
    beforeEach(() => mockWidth({ md: true, xlg: false }));
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

    it("the scale and Fovea | Disc edge never fold: Place ETDRS folds Delete, then Radius fraction, then Keep grid size; the circle folds its sizes", async () => {
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

describe("ToolOptionsBar with a form's point field armed", () => {
    afterEach(() => {
        pointArming.session = null;
    });

    function renderFormPoints(is3D: boolean) {
        const ws = workspaceWith(1);
        const tool = new PointTool({ coordinateSpace: "volume" });
        tool.points = [
            { x: 1, y: 2, index: 4 },
            { x: 5, y: 6, index: 7 },
        ];
        ws.attachViewport(0, {
            zoomPercent: 100,
            zoomBy: vi.fn(),
            reset: vi.fn(),
            layers: {
                viewerContext: {
                    image: { is3D },
                    keyboardCursor: { on: false },
                    returnFocus: vi.fn(),
                },
                formPointTool: tool,
            } as never,
        });
        pointArming.session = {
            key: "form:9101:lesions",
            label: "Lesion points",
            form: "AMD lesion points #9101",
            analysis: { coordinateSpace: "volume" },
        } as never;
        return render(ToolOptionsBar, { context: workspaceContext(ws) });
    }

    it("on the wrong kind of image says why in place of the field, with no stepper", () => {
        renderFormPoints(false);
        expect(screen.getByText("Form points")).toBeInTheDocument();
        expect(
            screen.getByText("These points go on an OCT volume. Select one."),
        ).toBeInTheDocument();
        expect(
            screen.queryByText("Lesion points · AMD lesion points #9101"),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("group", { name: "Points" }),
        ).not.toBeInTheDocument();
    });

    it("titles the Keys list Form points", async () => {
        renderFormPoints(true);
        await fireEvent.click(screen.getByRole("button", { name: "Keys" }));
        const dialog = await screen.findByRole("dialog", { name: "Keys" });
        expect(
            within(dialog)
                .getAllByRole("heading")
                .map((h) => h.textContent?.trim()),
        ).toEqual(["Form points", "Without a tool"]);
    });

    it("on the right image names the field and its form and shows the stepper", () => {
        renderFormPoints(true);
        expect(
            screen.getByText("Lesion points · AMD lesion points #9101"),
        ).toBeInTheDocument();
        expect(
            within(screen.getByRole("group", { name: "Points" })).getByText(
                "Point – / 2",
            ),
        ).toBeInTheDocument();
    });
});
