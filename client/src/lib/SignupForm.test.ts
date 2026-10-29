import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "$lib/api/client";
import SignupForm from "./SignupForm.svelte";

vi.mock("$app/paths", () => ({ resolve: (route: string) => route }));

describe("SignupForm", () => {
    it("reports a rejected sign-up, clears the password and focuses Username", async () => {
        const message = "An account with this username already exists.";
        const signup = vi.fn().mockRejectedValue(new ApiError(409, message));
        render(SignupForm, {
            context: new Map([["globalContext", { userManager: { signup } }]]),
        });
        const username = screen.getByLabelText("Username");
        const password = screen.getByLabelText("Password");
        await fireEvent.input(username, { target: { value: "ada" } });
        await fireEvent.input(password, {
            target: { value: "a-long-test-password" },
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Create account" }),
        );

        await waitFor(() => expect(username).toHaveFocus());
        expect(signup).toHaveBeenCalledWith("ada", "a-long-test-password");
        expect(screen.getByText("Account not created")).toBeInTheDocument();
        expect(screen.getByText(message)).toBeInTheDocument();
        expect(password).toHaveValue("");
    });
});
