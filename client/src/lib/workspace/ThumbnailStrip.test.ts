import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it } from "vitest";
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

describe("ThumbnailStrip", () => {
    it("tiles follow the catalogue, carry their slot number, and a click loads into the selected viewport", async () => {
        const ws = workspaceWith(3, { layout: "2x1" });
        const { container } = render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(ws),
        });
        const names = screen
            .getAllByRole("button")
            .map((b) => b.textContent ?? "");
        expect(names.map((n) => n.match(/img\d+/)?.[0])).toEqual([
            "img01",
            "img02",
            "img03",
        ]);
        expect(names[1]).toMatch(/In viewport\s*2/);
        expect(names[2]).not.toMatch(/In viewport/);
        ws.select(1);
        await fireEvent.click(screen.getByTestId("tile-img03"));
        expect(ws.slots.map((s) => s.imageId)).toEqual(["img01", "img03"]);
        await expectNoAxeViolations(container);
    });

    it("is one tab stop that arrow keys and Home / End move", async () => {
        render(ThumbnailStrip, {
            props: { tile, titleFor },
            context: workspaceContext(workspaceWith(3)),
        });
        const tiles = screen.getAllByRole("button");
        expect(tiles.map((b) => b.tabIndex)).toEqual([0, -1, -1]);
        await fireEvent.keyDown(tiles[0], { key: "ArrowRight" });
        await waitFor(() => expect(tiles[1]).toHaveFocus());
        expect(tiles.map((b) => b.tabIndex)).toEqual([-1, 0, -1]);
        await fireEvent.keyDown(tiles[1], { key: "End" });
        await waitFor(() => expect(tiles[2]).toHaveFocus());
        await fireEvent.keyDown(tiles[2], { key: "Home" });
        await waitFor(() => expect(tiles[0]).toHaveFocus());
    });
});
