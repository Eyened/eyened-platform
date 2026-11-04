import { fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import ViewportGrid from "./ViewportGrid.svelte";
import type { Workspace } from "./workspace.svelte";

const viewer = createRawSnippet((imageId: () => string) => ({
    render: () => `<div data-testid="viewer-${imageId()}"></div>`,
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
});
