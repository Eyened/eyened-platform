import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import SortHeader from "./SortHeader.svelte";

describe("SortHeader", () => {
    it("renders the label inside a button", () => {
        render(SortHeader, { props: { label: "Name", onclick: vi.fn() } });
        const button = screen.getByRole("button", { name: "Name" });
        expect(button).toBeInTheDocument();
    });

    it("calls onclick when the button is clicked", async () => {
        const onclick = vi.fn();
        render(SortHeader, { props: { label: "Name", onclick } });
        await fireEvent.click(screen.getByRole("button", { name: "Name" }));
        expect(onclick).toHaveBeenCalledTimes(1);
    });
});
