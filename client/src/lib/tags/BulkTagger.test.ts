import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import type { ImageGET, TagMeta } from "../../types/openapi_types";

vi.mock("$lib/data/helpers", () => ({
    tagInstance: vi.fn(),
    untagInstance: vi.fn(),
    createTag: vi.fn(),
}));

const { untagInstance } = await import("$lib/data/helpers");
const { default: BulkTagger } = await import("./BulkTagger.svelte");

const tag = { id: 3, name: "Blurry" } as unknown as TagMeta;
const images = ["a", "b"].map(
    (id) => ({ id, tags: [tag] }) as unknown as ImageGET,
);

describe("BulkTagger", () => {
    it("removes a tag from all images only after the confirm", async () => {
        render(BulkTagger, { props: { instances: images } });

        await fireEvent.click(screen.getByRole("button", { name: "Tag" }));
        await fireEvent.click(
            await screen.findByRole("button", {
                name: "Remove Blurry from all images",
            }),
        );

        expect(untagInstance).not.toHaveBeenCalled();
        expect(
            screen.getByText(
                "Remove Blurry from 2 images? Comments on it are deleted.",
            ),
        ).toBeTruthy();

        await fireEvent.click(screen.getByRole("button", { name: "Remove" }));
        await waitFor(() => expect(untagInstance).toHaveBeenCalledTimes(2));
    });
});
