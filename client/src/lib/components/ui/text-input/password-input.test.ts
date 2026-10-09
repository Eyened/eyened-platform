import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PasswordInput from "./password-input.svelte";

describe("PasswordInput", () => {
    it("toggles the input type and the toggle's label", async () => {
        render(PasswordInput, { props: { labelText: "Password" } });
        const input = screen.getByLabelText("Password");
        expect(input).toHaveAttribute("type", "password");

        await fireEvent.click(
            screen.getByRole("button", { name: "Show password" }),
        );

        expect(input).toHaveAttribute("type", "text");
        expect(
            screen.getByRole("button", { name: "Hide password" }),
        ).toBeInTheDocument();
    });
});
