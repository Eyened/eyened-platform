import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import ChangePasswordModal from "./ChangePasswordModal.svelte";

describe("ChangePasswordModal", () => {
    it("does not send a new password that does not match its confirmation", async () => {
        const changePassword = vi.fn(() => Promise.resolve());
        render(ChangePasswordModal, {
            props: { open: true },
            context: new Map([
                ["globalContext", { userManager: { changePassword } }],
            ]),
        });

        await fireEvent.input(screen.getByLabelText("Current password"), {
            target: { value: "old-password-123456" },
        });
        await fireEvent.input(screen.getByLabelText("New password"), {
            target: { value: "new-password-123456" },
        });
        await fireEvent.input(screen.getByLabelText("Confirm new password"), {
            target: { value: "new-password-12345X" },
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Change password" }),
        );

        expect(changePassword).not.toHaveBeenCalled();
        expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
});
