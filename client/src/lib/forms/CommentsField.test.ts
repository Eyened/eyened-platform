import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { SaveTracker } from "$lib/saving/saveTracker.svelte";
import CommentsField from "./CommentsField.svelte";

describe("CommentsField", () => {
    it("a failed save shows Couldn't save with Retry; after Retry it clears and focus is on the field", async () => {
        const send = vi
            .fn<(text: string) => Promise<void>>()
            .mockRejectedValueOnce(new Error("offline"))
            .mockResolvedValue(undefined);
        const saver = new DebouncedSaver<string>({
            kind: "comments",
            group: "comments",
            target: { to: "focus", focus: () => {} },
            delay: 0,
            send,
            tracker: new SaveTracker(),
        });
        render(CommentsField, { props: { saver, initial: "" } });
        await fireEvent.input(screen.getByLabelText("Comments"), {
            target: { value: "Blurry OS" },
        });
        await waitFor(() =>
            expect(screen.getByText("Couldn't save")).toBeInTheDocument(),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() =>
            expect(screen.queryByText("Couldn't save")).toBeNull(),
        );
        // Retry unmounted with the error, so focus went back to the field.
        expect(document.activeElement).toBe(screen.getByLabelText("Comments"));
    });
});
