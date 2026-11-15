import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ToggleGroup from "./toggle-group.svelte";

afterEach(cleanup);

const items = [
    { value: "off", text: "Off", label: "Off" },
    { value: "current", text: "Current", label: "Current slice" },
    { value: "all", text: "All", label: "All slices" },
];

function tabIndexes() {
    return screen.getAllByRole("radio").map((radio) => radio.tabIndex);
}

describe("ToggleGroup", () => {
    it("puts the one Tab stop on the value set by code, or on the first option when none matches", async () => {
        const { rerender } = render(ToggleGroup, {
            props: {
                value: "current",
                onchange: vi.fn(),
                items,
                label: "Localizer lines",
            },
        });
        expect(tabIndexes()).toEqual([-1, 0, -1]);

        await rerender({ value: "all" });
        expect(tabIndexes()).toEqual([-1, -1, 0]);

        await rerender({ value: "none" });
        expect(tabIndexes()).toEqual([0, -1, -1]);
    });
});
