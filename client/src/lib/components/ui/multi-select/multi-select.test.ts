import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import MultiSelect from "./multi-select.svelte";

const options = [
    { value: "1", label: "Drusen" },
    { value: "2", label: "Druse cluster" },
    { value: "3", label: "Haemorrhage" },
];

describe("MultiSelect", () => {
    it("keeps the typed filter after a pick, so the list stays filtered", async () => {
        render(MultiSelect, {
            props: { label: "Subfeatures", options, values: [] },
        });
        const input = screen.getByRole("combobox", { name: "Subfeatures" });

        await fireEvent.input(input, { target: { value: "dru" } });
        await fireEvent.pointerUp(
            await screen.findByRole("option", { name: "Drusen" }),
        );

        await waitFor(() => expect(input).toHaveValue("dru"));
        expect(
            screen.getByRole("option", { name: "Druse cluster" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("option", { name: "Haemorrhage" }),
        ).toBeNull();
    });

    it("highlights and toggles with the keyboard after typing a filter", async () => {
        render(MultiSelect, {
            props: { label: "Subfeatures", options, values: [] },
        });
        const input = screen.getByRole("combobox", { name: "Subfeatures" });

        await fireEvent.input(input, { target: { value: "e" } });
        await screen.findByRole("option", { name: "Haemorrhage" });
        await fireEvent.input(input, { target: { value: "er" } });
        await fireEvent.keyDown(input, { key: "ArrowDown" });
        await fireEvent.keyDown(input, { key: "Enter" });

        await waitFor(() =>
            expect(
                screen.getByRole("option", { name: "Druse cluster" }),
            ).toHaveAttribute("aria-selected", "true"),
        );
    });
});
