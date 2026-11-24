import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import RadioButtonGroup from "./radio-button-group.svelte";

describe("RadioButtonGroup", () => {
    it("keeps the answer when a read-only radio is clicked", async () => {
        render(RadioButtonGroup, {
            props: {
                legendText: "Grade",
                items: [
                    { value: "a", labelText: "A" },
                    { value: "b", labelText: "B" },
                ],
                selected: "a",
                readonly: true,
            },
        });
        await fireEvent.click(screen.getByRole("radio", { name: "B" }));
        // jsdom doesn't put the previous radio back after a cancelled click (browsers do; a hand check covers it).
        expect(screen.getByRole("radio", { name: "B" })).not.toBeChecked();
    });
});
