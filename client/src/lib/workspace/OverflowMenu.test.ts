import { fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it } from "vitest";
import OverflowMenu from "./OverflowMenu.svelte";

// A raw snippet's argument is a getter.
const children = createRawSnippet((close: () => () => void) => ({
    render: () => `<button type="button" data-testid="item">Close it</button>`,
    setup: (el: Element) => {
        el.addEventListener("click", () => close()());
    },
}));

function renderMenu() {
    const outside = document.createElement("button");
    document.body.append(outside);
    render(OverflowMenu, { props: { label: "More", children } });
    const trigger = screen.getByRole("button", { name: "More" });
    return { trigger, outside };
}

describe("OverflowMenu", () => {
    it("shows its items when opened and hides them again", async () => {
        const { trigger } = renderMenu();
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        expect(screen.queryByRole("button", { name: "Close it" })).toBeNull();
        await fireEvent.click(trigger);
        expect(trigger).toHaveAttribute("aria-expanded", "true");
        expect(
            screen.getByRole("button", { name: "Close it" }),
        ).toBeInTheDocument();
    });

    it("stays open when focus leaves to nowhere, closes when it moves outside", async () => {
        const { trigger, outside } = renderMenu();
        await fireEvent.click(trigger);
        await fireEvent.focusOut(trigger, { relatedTarget: null });
        expect(trigger).toHaveAttribute("aria-expanded", "true");
        await fireEvent.focusOut(trigger, { relatedTarget: outside });
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        outside.remove();
    });

    it("Esc closes it and returns focus to the button", async () => {
        const { trigger } = renderMenu();
        await fireEvent.click(trigger);
        screen.getByTestId("item").focus();
        await fireEvent.keyDown(screen.getByTestId("item", { hidden: true }), {
            key: "Escape",
        });
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        expect(trigger).toHaveFocus();
    });

    it("an item that calls close() hides the list and refocuses the button", async () => {
        const { trigger } = renderMenu();
        await fireEvent.click(trigger);
        await fireEvent.click(screen.getByTestId("item"));
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        expect(trigger).toHaveFocus();
    });
});
