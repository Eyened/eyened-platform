import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IMAGE_MIME, SLOT_MIME } from "./dragTypes";
import {
    expectNoAxeViolations,
    workspaceContext,
    NO_URL,
    workspaceWith,
} from "./testUtils";
import ViewportGrid from "./ViewportGrid.svelte";
import { Workspace } from "./workspace.svelte";

const viewer = createRawSnippet((imageId: () => string) => ({
    render: () => `<div tabindex="0" data-testid="viewer-${imageId()}"></div>`,
}));
const titleFor = (imageId: string) => ({
    patient: "P-000417",
    rest: `OD · CF F1 · 2023-05-04 · ${imageId}`,
});

function renderGrid(ws: Workspace) {
    const onchooseimage = vi.fn();
    const result = render(ViewportGrid, {
        props: { viewer, titleFor, onchooseimage },
        context: workspaceContext(ws),
    });
    return { onchooseimage, ...result };
}

describe("ViewportGrid", () => {
    it("says Loading… with no Choose button until the workspace has hydrated", async () => {
        const ws = new Workspace();
        renderGrid(ws);
        expect(
            screen.getByRole("group", { name: "Viewport 1: Loading…" }),
        ).toHaveTextContent("Loading…");
        expect(screen.getByText("Loading images…")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Choose an image" }),
        ).not.toBeInTheDocument();
        ws.hydrate([], NO_URL, null);
        expect(
            await screen.findByRole("button", { name: "Choose an image" }),
        ).toBeInTheDocument();
        expect(screen.queryByText("Loading images…")).not.toBeInTheDocument();
        expect(
            screen.getByRole("group", { name: "Viewport 1: Empty" }),
        ).toBeInTheDocument();
    });

    it("names each viewport; only the selected one's controls are tab stops", async () => {
        const ws = workspaceWith(3, { layout: "2x2" });
        const { container } = renderGrid(ws);
        const first = screen.getByRole("group", {
            name: "Viewport 1: P-000417 OD · CF F1 · 2023-05-04 · img01",
        });
        expect(first).toHaveAttribute("aria-current", "true");
        expect(
            screen.getByRole("group", { name: "Viewport 4: Empty" }),
        ).toBeInTheDocument();
        const maximise = screen.getAllByRole("button", { name: "Maximise" });
        expect(maximise.map((b) => b.tabIndex)).toEqual([0, -1, -1, -1]);
        expect(screen.getAllByRole("separator")).toHaveLength(2);
        await expectNoAxeViolations(container);
    });

    it("empties a viewport on close and offers to choose an image", async () => {
        const ws = workspaceWith(2, { layout: "2x1" });
        const { onchooseimage } = renderGrid(ws);
        await fireEvent.click(
            screen.getAllByRole("button", { name: "Close" })[1],
        );
        expect(
            screen.getByRole("group", { name: "Viewport 2: Empty" }),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Choose an image" }),
        );
        expect(ws.selected).toBe(1);
        expect(onchooseimage).toHaveBeenCalled();
    });

    it("turns the page with Shift + Page Down and announces it", async () => {
        const ws = workspaceWith(6, { layout: "2x2" });
        renderGrid(ws);
        await fireEvent.keyDown(screen.getByTestId("viewer-img01"), {
            key: "PageDown",
            shiftKey: true,
        });
        expect(ws.page).toBe(2);
        expect(screen.getByText("Page 2 of 2, images 5–6")).toBeInTheDocument();
    });

    it("keeps focus in the viewport after a page turn or a step loads a new image", async () => {
        const ws = workspaceWith(6, { layout: "2x2" });
        renderGrid(ws);
        screen.getByTestId("viewer-img01").focus();
        await fireEvent.keyDown(document.activeElement!, {
            key: "PageDown",
            shiftKey: true,
        });
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getByTestId("viewer-img05"),
            ),
        );
        await fireEvent.keyDown(document.activeElement!, { key: "PageUp" });
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getByTestId("viewer-img04"),
            ),
        );
    });

    it("moves focus to Choose an image when a page turn empties the focused viewport", async () => {
        const ws = workspaceWith(6, { layout: "2x2" });
        renderGrid(ws);
        screen.getByTestId("viewer-img03").focus();
        await fireEvent.keyDown(document.activeElement!, {
            key: "PageDown",
            shiftKey: true,
        });
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getAllByRole("button", { name: "Choose an image" })[0],
            ),
        );
        expect(
            screen.getByRole("group", { name: "Viewport 3: Empty" }),
        ).toContainElement(document.activeElement as HTMLElement);
    });

    it("maximises into a strip on the same frame nodes, without splitters", async () => {
        const ws = workspaceWith(4, { layout: "2x2" });
        ws.strip = false;
        renderGrid(ws);
        const second = screen.getByRole("group", { name: /^Viewport 2:/ });
        await fireEvent.click(
            screen.getAllByRole("button", { name: "Maximise" })[0],
        );
        expect(screen.getByRole("group", { name: /^Viewport 2:/ })).toBe(
            second,
        );
        expect(second).toHaveAttribute("data-mode", "tile");
        expect(screen.queryAllByRole("separator")).toHaveLength(0);
        await fireEvent.click(second);
        expect(ws.maximised).toBe(1);
    });

    it("with the thumbnail strip on, maximise hides the other viewports without rebuilding them", async () => {
        const ws = workspaceWith(4, { layout: "2x2" });
        renderGrid(ws);
        const second = screen.getByRole("group", { name: /^Viewport 2:/ });
        await fireEvent.click(
            screen.getAllByRole("button", { name: "Maximise" })[0],
        );
        expect(second.isConnected).toBe(true);
        expect(second).toHaveAttribute("data-mode", "hidden");
        expect(
            screen.getByRole("group", { name: /^Viewport 1:/ }),
        ).toHaveAttribute("data-mode", "big");
    });

    describe("drag and drop", () => {
        const transfer = (data: Record<string, string>) => ({
            types: Object.keys(data),
            getData: (type: string) => data[type] ?? "",
            setData: vi.fn(),
            effectAllowed: "none",
        });
        const frame = (n: number) =>
            screen.getByRole("group", { name: new RegExp(`^Viewport ${n}:`) });

        it("swaps two viewports when one's title bar is dropped on the other", async () => {
            const ws = workspaceWith(2, { layout: "2x1" });
            renderGrid(ws);
            const dataTransfer = transfer({});
            await fireEvent.dragStart(
                frame(1).querySelector(".titlebar") as Element,
                { dataTransfer },
            );
            expect(dataTransfer.setData).toHaveBeenCalledWith(SLOT_MIME, "0");
            await fireEvent.dragOver(frame(2), {
                dataTransfer: transfer({ [SLOT_MIME]: "0" }),
            });
            expect(frame(2)).toHaveClass("drop-target");
            await fireEvent.drop(frame(2), {
                dataTransfer: transfer({ [SLOT_MIME]: "0" }),
            });
            expect(ws.slots.map((s) => s.imageId)).toEqual(["img02", "img01"]);
            expect(frame(2)).not.toHaveClass("drop-target");
        });

        it("loads a dragged catalogue image into the frame it lands on and selects it", async () => {
            const ws = workspaceWith(3, { layout: "2x1" });
            renderGrid(ws);
            await fireEvent.drop(frame(2), {
                dataTransfer: transfer({ [IMAGE_MIME]: "img03" }),
            });
            expect(ws.slots[1].imageId).toBe("img03");
            expect(ws.selected).toBe(1);
        });

        it("ignores a drag it does not know and clears the highlight on leave", async () => {
            const ws = workspaceWith(2, { layout: "2x1" });
            renderGrid(ws);
            const unknown = { dataTransfer: transfer({ "text/plain": "x" }) };
            await fireEvent.dragOver(frame(2), unknown);
            expect(frame(2)).not.toHaveClass("drop-target");
            await fireEvent.dragOver(frame(2), {
                dataTransfer: transfer({ [IMAGE_MIME]: "img01" }),
            });
            await fireEvent.dragLeave(frame(2), { relatedTarget: null });
            expect(frame(2)).not.toHaveClass("drop-target");
        });

        it("does not start a drag from an empty viewport", async () => {
            const ws = workspaceWith(1, { layout: "2x1" });
            renderGrid(ws);
            const dataTransfer = transfer({});
            await fireEvent.dragStart(
                frame(2).querySelector(".titlebar") as Element,
                { dataTransfer },
            );
            expect(dataTransfer.setData).not.toHaveBeenCalled();
        });
    });

    describe("splitters", () => {
        afterEach(() => vi.restoreAllMocks());

        function renderSized() {
            vi.spyOn(
                HTMLElement.prototype,
                "clientWidth",
                "get",
            ).mockReturnValue(1000);
            vi.spyOn(
                HTMLElement.prototype,
                "clientHeight",
                "get",
            ).mockReturnValue(600);
            const ws = workspaceWith(2, { layout: "2x1" });
            renderGrid(ws);
            return ws;
        }

        it("Home and End move the column splitter to its limits and Enter resets it", async () => {
            const ws = renderSized();
            const splitter = screen.getByRole("separator");
            await fireEvent.keyDown(splitter, { key: "Home" });
            const [min] = ws.colSizes;
            expect(min).toBeLessThan(1);
            await fireEvent.keyDown(splitter, { key: "End" });
            expect(ws.colSizes[0]).toBeGreaterThan(1);
            await fireEvent.keyDown(splitter, { key: "Enter" });
            expect(ws.colSizes).toEqual([1, 1]);
        });

        it("an arrow key nudges the splitter along its axis", async () => {
            const ws = renderSized();
            await fireEvent.keyDown(screen.getByRole("separator"), {
                key: "ArrowRight",
            });
            expect(ws.colSizes[0]).toBeGreaterThan(1);
            expect(ws.colSizes[1]).toBeLessThan(1);
        });

        it("dragging moves the splitter", async () => {
            const ws = renderSized();
            const splitter = screen.getByRole("separator");
            await fireEvent.pointerDown(splitter, {
                clientX: 100,
                clientY: 0,
                pointerId: 1,
            });
            await fireEvent.pointerMove(splitter, {
                clientX: 160,
                clientY: 0,
                pointerId: 1,
            });
            expect(ws.colSizes[0]).toBeGreaterThan(1);
            await fireEvent.pointerUp(splitter, { pointerId: 1 });
            expect(ws.colSizes[0]).toBeGreaterThan(1);
        });

        it("Escape on a picked-up splitter restores the tracks", async () => {
            const ws = renderSized();
            const splitter = screen.getByRole("separator");
            const at = { clientX: 100, clientY: 0, pointerId: 1 };
            await fireEvent.pointerDown(splitter, at);
            await fireEvent.pointerUp(splitter, at);
            await fireEvent.pointerMove(screen.getByTestId("splitter-pickup"), {
                clientX: 160,
                clientY: 0,
            });
            expect(ws.colSizes[0]).toBeGreaterThan(1);
            await fireEvent.keyDown(splitter, { key: "Escape" });
            expect(ws.colSizes).toEqual([1, 1]);
        });
    });
});
