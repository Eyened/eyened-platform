import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { theme } from "$lib/theme.svelte";
import ProfilePopover from "./ProfilePopover.svelte";

afterEach(() => localStorage.clear());

describe("ProfilePopover", () => {
    it("saves the theme picked in the popover and applies it", async () => {
        render(ProfilePopover, {
            context: new Map([
                ["globalContext", { userManager: { user: { username: "u" } } }],
            ]),
        });
        await fireEvent.click(screen.getByRole("button", { name: "u" }));

        const themes = screen.getByRole("group", { name: "Theme" });
        await fireEvent.click(
            within(themes).getByRole("button", { name: "Light" }),
        );

        expect(localStorage.getItem("eyened:theme")).toBe("light");
        expect(theme.forPath("/library")).toBe("light");
        expect(
            within(themes).getByRole("button", { name: "Light" }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(
            within(themes).getByRole("button", { name: "System" }),
        ).toHaveAttribute("aria-pressed", "false");
    });
});
