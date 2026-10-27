import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

// Main needs the app context; a plain div wrapper stands in for it.
vi.mock(
    "$lib/components/Main.svelte",
    () => import("$lib/components/ui/table/table-toolbar.svelte"),
);
vi.mock("$lib/data/api", () => ({ fetchTasks: () => new Promise(() => {}) }));

const { default: Page } = await import("./+page.svelte");

describe("/tasks", () => {
    it("shows a busy table skeleton while tasks load", () => {
        render(Page);
        expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    });
});
