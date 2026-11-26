import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import ThumbnailStrip from "./ThumbnailStrip.svelte";

const tile = createRawSnippet((imageId: () => string) => ({
    render: () => `<div data-testid="tile-${imageId()}"></div>`,
}));
const titleFor = (imageId: string) => ({ patient: "P-000417", rest: imageId });

/** The tiles' title buttons, which hold the strip's tab stop. */
const titles = () => [
    ...document.querySelectorAll<HTMLButtonElement>("[data-tile-index]"),
];
const copies = () => screen.getAllByRole("button", { name: "Copy public ID" });

describe("ThumbnailStrip", () => {
    it("tiles follow the catalogue, carry their slot number; a click loads nothing, a double-click loads into the selected viewport", async () => {
        const ws = workspaceWith(3, { layout: "2x1" });
        const { container } = render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(ws),
        });
        const names = titles().map((b) => b.textContent ?? "");
        expect(names.map((n) => n.match(/img\d+/)?.[0])).toEqual([
            "img01",
            "img02",
            "img03",
        ]);
        expect(names[1]).toMatch(/In viewport\s*2/);
        expect(names[2]).not.toMatch(/In viewport/);
        ws.select(1);
        await fireEvent.click(screen.getByTestId("tile-img03"));
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img02"]);
        await fireEvent.dblClick(screen.getByTestId("tile-img03"));
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img03"]);
        await expectNoAxeViolations(container);
    });

    it("Enter and Space on a tile load it into the selected viewport", async () => {
        const ws = workspaceWith(3, { layout: "2x1" });
        render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(ws),
        });
        ws.select(1);
        await fireEvent.keyDown(titles()[2], { key: "Enter" });
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img03"]);
        await fireEvent.keyDown(titles()[0], { key: " " });
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img01"]);
    });

    it("is one tab stop that arrow keys and Home / End move", async () => {
        render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(workspaceWith(3)),
        });
        const tiles = titles();
        expect(tiles.map((b) => b.tabIndex)).toEqual([0, -1, -1]);
        await fireEvent.keyDown(tiles[0], { key: "ArrowRight" });
        await waitFor(() => expect(tiles[1]).toHaveFocus());
        expect(tiles.map((b) => b.tabIndex)).toEqual([-1, 0, -1]);
        expect(copies().map((b) => b.tabIndex)).toEqual([-1, 0, -1]);
        await fireEvent.keyDown(tiles[1], { key: "End" });
        await waitFor(() => expect(tiles[2]).toHaveFocus());
        await fireEvent.keyDown(tiles[2], { key: "Home" });
        await waitFor(() => expect(tiles[0]).toHaveFocus());
    });

    it("copies the tile's public ID without loading the tile", async () => {
        const writeText = vi.fn(() => Promise.resolve());
        Object.assign(navigator, { clipboard: { writeText } });
        const ws = workspaceWith(3, { layout: "2x1" });
        render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(ws),
        });
        ws.select(1);
        await fireEvent.click(copies()[2]);
        await fireEvent.dblClick(copies()[2]);
        expect(writeText).toHaveBeenCalledWith("img03");
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img02"]);
    });
});
