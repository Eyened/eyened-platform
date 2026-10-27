import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { TagMeta } from "../../types/openapi_types";
import Tagger from "./Tagger.svelte";

const tag = {
    id: 3,
    name: "Blurry",
    tagger: { id: 1, name: "A grader" },
    date: "2026-01-01T00:00:00Z",
    comment: null,
} as unknown as TagMeta;

describe("Tagger", () => {
    it("keeps the popover open with an inline error when a remove fails", async () => {
        const untag = vi.fn().mockRejectedValue(new Error("Not allowed"));
        render(Tagger, {
            props: {
                tagType: "Study",
                tags: [tag],
                tag: vi.fn(),
                untag,
                onUpdate: vi.fn(),
            },
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Edit tags" }),
        );
        await fireEvent.click(
            await screen.findByRole("button", { name: "Remove Blurry" }),
        );

        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toContain("Could not remove Blurry");
        expect(alert.textContent).toContain("Not allowed");
        expect(screen.getByRole("dialog", { name: "Edit tags" })).toBeTruthy();
    });
});
