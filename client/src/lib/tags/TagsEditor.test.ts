import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { createTag } from "$lib/data/helpers";
import TagsEditor from "./TagsEditor.svelte";

vi.mock("$lib/data/helpers", () => ({
    createTag: vi.fn(),
    deleteTag: vi.fn(),
}));

describe("TagsEditor", () => {
    it("shows a failed create and keeps the typed name", async () => {
        vi.mocked(createTag).mockRejectedValue(new Error("Name taken"));
        // Minimal context: TagsEditor only reads userManager.starredTagIds.
        const context = new Map([
            ["globalContext", { userManager: { starredTagIds: [] } }],
        ]);
        render(TagsEditor, { context });

        const name = screen.getByLabelText("Name") as HTMLInputElement;
        await fireEvent.input(name, { target: { value: " Blurry " } });
        await fireEvent.submit(name.closest("form")!);

        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toContain("Could not create Blurry");
        expect(alert.textContent).toContain("Name taken");
        expect(name.value).toBe(" Blurry ");
    });
});
