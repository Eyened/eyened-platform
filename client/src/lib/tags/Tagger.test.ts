import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { IconButton } from "$lib/components/ui/icon-button/index.js";
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

    it("closes the popover on a click on an icon button showing its tooltip", async () => {
        render(Tagger, {
            props: {
                tagType: "Study",
                tags: [tag],
                tag: vi.fn(),
                untag: vi.fn(),
                onUpdate: vi.fn(),
            },
        });
        render(IconButton, {
            props: {
                label: "Image information",
                children: createRawSnippet(() => ({
                    render: () => "<span></span>",
                })),
            },
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Edit tags" }),
        );
        await screen.findByRole("dialog", { name: "Edit tags" });
        const info = screen.getByRole("button", { name: "Image information" });
        await fireEvent.pointerMove(info, { pointerType: "mouse" });
        await waitFor(() =>
            expect(info.getAttribute("data-state")).toBe("delayed-open"),
        );

        // bits-ui registers the open tooltip as a dismissible layer a tick later.
        await new Promise((r) => setTimeout(r, 50));
        // Off the zero-size jsdom rects, so bits-ui counts it as outside the popover.
        await fireEvent.pointerDown(info, {
            button: 0,
            clientX: 10,
            clientY: 10,
        });

        await waitFor(() =>
            expect(
                screen.queryByRole("dialog", { name: "Edit tags" }),
            ).toBeNull(),
        );
    });
});
