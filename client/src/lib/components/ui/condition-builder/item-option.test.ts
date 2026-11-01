import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ItemOption from "./item-option.svelte";

const options = [
    "Study Tag Name",
    "Study Date",
    "Study Instance UID",
    "Study Description",
    "Study Round",
].map((label) => ({ id: label, label }));

describe("ItemOption", () => {
    it("lists an exact match first", async () => {
        render(ItemOption, {
            props: {
                options,
                selected: [],
                label: "Properties",
                onselect: () => {},
            },
        });

        await fireEvent.input(screen.getByLabelText("Search properties"), {
            target: { value: "Study Date" },
        });

        await waitFor(() =>
            expect(screen.getAllByRole("option")[0]).toHaveTextContent(
                "Study Date",
            ),
        );
    });
});
