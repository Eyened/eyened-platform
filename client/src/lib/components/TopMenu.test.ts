import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/svelte";

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));
vi.mock("$app/state", () => ({
    page: { url: new URL("http://localhost/tasks") },
}));

const { default: TopMenu } = await import("./TopMenu.svelte");

const context = new Map([
    [
        "globalContext",
        { userManager: { user: { username: "u", is_admin: false } } },
    ],
]);

async function openSideNav() {
    render(TopMenu, { context });
    await fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    return screen.getByRole("navigation", { name: "Side navigation" });
}

describe("side nav", () => {
    it("opens from the menu button with the section links", async () => {
        const sideNav = await openSideNav();
        expect(
            within(sideNav).getByRole("link", { name: "Tasks" }),
        ).toHaveAttribute("aria-current", "page");
        expect(
            within(sideNav).getByRole("link", { name: "Browser" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Close menu" }),
        ).toHaveAttribute("aria-expanded", "true");
    });

    it("closes on Escape and returns focus to the menu button", async () => {
        const sideNav = await openSideNav();
        await fireEvent.keyDown(sideNav, { key: "Escape" });
        expect(
            screen.queryByRole("navigation", { name: "Side navigation" }),
        ).toBeNull();
        expect(screen.getByRole("button", { name: "Open menu" })).toHaveFocus();
    });

    it("closes when a link is chosen", async () => {
        const sideNav = await openSideNav();
        await fireEvent.click(
            within(sideNav).getByRole("link", { name: "Browser" }),
        );
        expect(
            screen.queryByRole("navigation", { name: "Side navigation" }),
        ).toBeNull();
    });

    it("closes when focus leaves the side nav", async () => {
        const sideNav = await openSideNav();
        await fireEvent.focusOut(
            within(sideNav).getByRole("link", { name: "Tasks" }),
            { relatedTarget: screen.getByRole("button", { name: "u" }) },
        );
        expect(
            screen.queryByRole("navigation", { name: "Side navigation" }),
        ).toBeNull();
    });
});
