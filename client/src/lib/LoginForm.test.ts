import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "$lib/api/client";
import { authClient } from "../auth";
import LoginForm from "./LoginForm.svelte";

function renderForm(login = vi.fn()) {
    vi.spyOn(authClient, "options").mockResolvedValue({
        password_enabled: true,
        oidc_enabled: true,
        oidc_provider_name: "SURF",
    });
    render(LoginForm, {
        context: new Map([["globalContext", { userManager: { login } }]]),
    });
    return login;
}

afterEach(() => vi.unstubAllGlobals());

describe("LoginForm", () => {
    it("reports each empty field on submit and focuses Username", async () => {
        const login = renderForm();
        const username = await screen.findByLabelText("Username");
        const password = screen.getByLabelText("Password");

        await fireEvent.click(screen.getByRole("button", { name: "Log in" }));

        expect(username).toHaveAccessibleDescription("Username is required");
        expect(password).toHaveAccessibleDescription("Password is required");
        await waitFor(() => expect(username).toHaveFocus());
        expect(login).not.toHaveBeenCalled();

        await fireEvent.input(username, { target: { value: "ada" } });

        expect(username).not.toHaveAccessibleDescription();
        expect(password).toHaveAccessibleDescription("Password is required");
    });

    it.each([
        {
            error: new ApiError(401, "Unauthorized"),
            title: "Incorrect username or password",
            subtitle: "Try again.",
        },
        {
            error: new ApiError(500, "Database unavailable"),
            title: "Log in failed",
            subtitle: "Database unavailable",
        },
    ])(
        "reports a $error.status rejection and focuses Username",
        async ({ error, title, subtitle }) => {
            renderForm(vi.fn().mockRejectedValue(error));
            const username = await screen.findByLabelText("Username");
            const password = screen.getByLabelText("Password");
            await fireEvent.input(username, { target: { value: "ada" } });
            await fireEvent.input(password, { target: { value: "wrong" } });
            // The notification has no live role; it must be Username's
            // description by the time focus lands there.
            let describedAtFocus = "";
            username.addEventListener("focus", () => {
                describedAtFocus = (
                    username.getAttribute("aria-describedby") ?? ""
                )
                    .split(" ")
                    .map((id) => document.getElementById(id)?.textContent ?? "")
                    .join(" ");
            });

            await fireEvent.click(
                screen.getByRole("button", { name: "Log in" }),
            );

            await waitFor(() => expect(username).toHaveFocus());
            expect(screen.getByText(title)).toBeInTheDocument();
            expect(screen.getByText(subtitle)).toBeInTheDocument();
            expect(password).toHaveValue("");
            expect(screen.queryByRole("alert")).toBeNull();
            expect(describedAtFocus).toContain(title);
        },
    );

    it("keeps the OIDC error on the page", async () => {
        // jsdom ignores href assignments on the real location, so stub it.
        const location = {
            href: "http://localhost/users/login",
            origin: "http://localhost",
            search: "",
        };
        vi.stubGlobal("location", location);
        vi.spyOn(authClient, "OIDCAuthorize").mockRejectedValue(
            new Error("OIDC authorize failed"),
        );
        renderForm();

        await fireEvent.click(
            await screen.findByRole("button", { name: "Log in with SURF" }),
        );

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "OIDC authorize failed",
        );
        expect(location.href).toBe("http://localhost/users/login");
    });
});
