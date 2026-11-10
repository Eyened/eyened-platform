import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Pager from "./Pager.svelte";
import { workspaceContext, workspaceWith } from "./testUtils";
import type { Workspace } from "./workspace.svelte";

const renderPager = (ws: Workspace) =>
    render(Pager, { context: workspaceContext(ws) });

describe("Pager", () => {
    it("turns the page from the button named with its shortcut", async () => {
        const ws = workspaceWith(6, { layout: "2x2" });
        renderPager(ws);
        await fireEvent.click(
            screen.getByRole("button", {
                name: "Next page (Shift + Page Down)",
            }),
        );
        expect(ws.page).toBe(2);
    });
});
