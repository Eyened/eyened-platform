import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import DatePicker from "./date-picker.svelte";

describe("DatePicker", () => {
    it("drops the invalid-date error when the value is reset from outside", async () => {
        const { rerender } = render(DatePicker, {
            props: { labelText: "Study date", value: "" },
        });
        const input = screen.getByLabelText("Study date");

        await fireEvent.input(input, { target: { value: "2024-13-99" } });
        await fireEvent.change(input);
        expect(input).toHaveAttribute("aria-invalid", "true");

        await rerender({ value: "" });

        expect(input).not.toHaveAttribute("aria-invalid");
        expect(screen.queryByText("Enter a date as yyyy-mm-dd")).toBeNull();
    });
});
