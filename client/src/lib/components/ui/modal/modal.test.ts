import { fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";
import Modal from "./modal.svelte";

const body = createRawSnippet(() => ({ render: () => "<p>Body</p>" }));

function renderModal(onsubmit: () => false | Promise<unknown>) {
    render(Modal, {
        props: {
            open: true,
            modalHeading: "Edit task",
            primaryButtonText: "Save",
            primaryButtonLoadingDescription: "Saving…",
            successDescription: "Saved",
            errorTitle: "Task could not be saved",
            onsubmit,
            children: body,
        },
    });
}

describe("Modal", () => {
    it("stays open and shows the error when the submit fails", async () => {
        renderModal(() => Promise.reject(new Error("Forbidden")));

        await fireEvent.click(screen.getByRole("button", { name: "Save" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
        expect(screen.getByRole("dialog")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Save" }),
        ).not.toHaveAttribute("aria-disabled", "true");
    });

    it("submits once and cannot be closed while pending", async () => {
        const onsubmit = vi.fn(() => new Promise(() => {}));
        renderModal(onsubmit);
        const save = screen.getByRole("button", { name: "Save" });

        await fireEvent.click(save);
        await fireEvent.click(save);
        await fireEvent.keyDown(document.activeElement ?? document.body, {
            key: "Escape",
        });

        expect(onsubmit).toHaveBeenCalledOnce();
        expect(save).toHaveAttribute("aria-disabled", "true");
        expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
});
