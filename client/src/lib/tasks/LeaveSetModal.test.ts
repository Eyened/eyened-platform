import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import LeaveSetModal from "./LeaveSetModal.svelte";

describe("LeaveSetModal", () => {
    it("says the set won't be marked ready as a second sentence", async () => {
        render(LeaveSetModal, {
            setNumber: 12,
            markReady: true,
            onanswer: () => {},
        });
        const dialog = await screen.findByRole("dialog");
        expect(dialog.querySelector("p")?.textContent?.trim()).toBe(
            "Some of your work in set 12 isn't saved. Set 12 won't be marked ready.",
        );
    });
});
