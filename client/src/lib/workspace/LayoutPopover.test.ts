import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import LayoutPopover from "./LayoutPopover.svelte";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "./testUtils";

async function open(ws = workspaceWith(20)) {
    const result = render(LayoutPopover, { context: workspaceContext(ws) });
    await fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    await screen.findByRole("button", { name: "One viewport" });
    return { ws, ...result };
}

describe("LayoutPopover", () => {
    it("moves focus with the arrow keys without applying; a click applies", async () => {
        const { ws, container } = await open();
        const current = screen.getByRole("button", { name: "One viewport" });
        expect(current).toHaveAttribute("aria-pressed", "true");
        expect(current.tabIndex).toBe(0);
        await fireEvent.keyDown(current, { key: "ArrowDown" });
        const next = screen.getByRole("button", { name: "2 side by side" });
        await waitFor(() => expect(next).toHaveFocus());
        expect(next.tabIndex).toBe(0);
        expect(ws.preset.id).toBe("1x1");
        await fireEvent.click(next);
        expect(ws.preset.id).toBe("2x1");
        expect(screen.getByText("20 open: 2 pages")).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("names the row that fits the open images for screen readers", async () => {
        await open(workspaceWith(11));
        expect(
            screen.getByRole("group", { name: "12 viewports" }),
        ).toHaveTextContent("Fits 11 open images");
    });

    it("closes when focus leaves it", async () => {
        await open();
        await fireEvent.focusOut(
            screen.getByRole("button", { name: "By visit" }),
            {
                relatedTarget: document.body,
            },
        );
        await waitFor(() =>
            expect(
                screen.queryByRole("button", { name: "One viewport" }),
            ).toBeNull(),
        );
    });
});
