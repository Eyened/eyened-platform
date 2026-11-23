import { render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import IncompleteFormsModal from "./IncompleteFormsModal.svelte";

const lines = Array.from(
    { length: 7 },
    (_, i) =>
        `Image quality grading for OD · OCT · 2024-05-0${i + 1}: not complete`,
);

describe("IncompleteFormsModal", () => {
    it("names the state, lists five forms and the rest as a number, and starts on Go back", async () => {
        render(IncompleteFormsModal, {
            props: { setNumber: 12, lines, last: false, onanswer: vi.fn() },
        });
        expect(
            screen.getByRole("heading", { name: "7 forms aren't complete" }),
        ).toBeInTheDocument();
        expect(screen.getAllByRole("listitem")).toHaveLength(5);
        expect(screen.getByText("and 2 more")).toBeInTheDocument();
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getByRole("button", { name: "Go back" }),
            ),
        );
        expect(
            screen.getByRole("button", { name: "Mark ready and next" }),
        ).toBeInTheDocument();
    });
});
