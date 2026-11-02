import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ComboBox from "./combo-box.svelte";

const all = [
    { id: "1", text: "Drusen" },
    { id: "2", text: "Druse cluster" },
    { id: "3", text: "Haemorrhage" },
];

describe("ComboBox", () => {
    it("highlights and picks with the keyboard after typing a filter", async () => {
        let value = $state("");
        const picked: string[] = [];
        render(ComboBox, {
            props: {
                titleText: "Tag",
                get value() {
                    return value;
                },
                set value(v: string) {
                    value = v;
                },
                get items() {
                    return all.filter((i) =>
                        i.text.toLowerCase().includes(value.toLowerCase()),
                    );
                },
                onselect: (id: string) => picked.push(id),
            },
        });
        const input = screen.getByRole("combobox", { name: "Tag" });

        await fireEvent.input(input, { target: { value: "e" } });
        await screen.findByRole("option", { name: "Haemorrhage" });
        await fireEvent.input(input, { target: { value: "er" } });
        await fireEvent.keyDown(input, { key: "ArrowDown" });
        await fireEvent.keyDown(input, { key: "Enter" });

        await waitFor(() => expect(picked).toEqual(["2"]));
    });
});
