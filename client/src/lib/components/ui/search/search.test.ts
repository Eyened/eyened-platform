import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Search } from "./index.js";

const outside = vi.fn();
afterEach(() => document.removeEventListener("keydown", outside));

describe("Search", () => {
    it("Esc with text clears it and stops there; Esc when empty passes on", async () => {
        render(Search, { props: { labelText: "Search keys", value: "space" } });
        document.addEventListener("keydown", outside);
        const box = screen.getByRole("searchbox", { name: "Search keys" });

        await fireEvent.keyDown(box, { key: "Escape" });
        expect(box).toHaveValue("");
        expect(outside).not.toHaveBeenCalled();

        await fireEvent.keyDown(box, { key: "Escape" });
        expect(outside).toHaveBeenCalledTimes(1);
    });
});
