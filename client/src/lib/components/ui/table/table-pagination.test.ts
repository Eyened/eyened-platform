import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Pagination from "./table-pagination.svelte";

function renderPagination(page: number) {
    const onchange = vi.fn();
    render(Pagination, {
        props: {
            page,
            pageSize: 20,
            pageSizes: [10, 20, 50, 100],
            totalItems: 340,
            onchange,
        },
    });
    return onchange;
}

const button = (name: string) => screen.getByRole("button", { name });

describe("Table.Pagination", () => {
    it("shows the item range and the page count", () => {
        renderPagination(2);
        expect(screen.getByText("21–40 of 340 items")).toBeInTheDocument();
        expect(screen.getByText("of 17 pages")).toBeInTheDocument();
        expect(button("Previous page")).not.toHaveAttribute("aria-disabled");
    });

    it("marks the ends aria-disabled", () => {
        renderPagination(1);
        expect(button("Previous page")).toHaveAttribute(
            "aria-disabled",
            "true",
        );
        expect(button("Next page")).not.toHaveAttribute("aria-disabled");
    });

    it("shows the last range and disables Next on the last page", () => {
        renderPagination(17);
        expect(screen.getByText("321–340 of 340 items")).toBeInTheDocument();
        expect(button("Next page")).toHaveAttribute("aria-disabled", "true");
    });

    it("moves focus to Previous on reaching the last page", async () => {
        const onchange = renderPagination(16);
        button("Next page").focus();
        await fireEvent.click(button("Next page"));
        expect(onchange).toHaveBeenCalledWith({ page: 17, pageSize: 20 });
        await waitFor(() =>
            expect(document.activeElement).toBe(button("Previous page")),
        );
    });

    it("goes back to page 1 when the page size changes", async () => {
        const onchange = renderPagination(5);
        await fireEvent.change(screen.getByLabelText("Items per page:"), {
            target: { value: "50" },
        });
        expect(onchange).toHaveBeenCalledWith({ page: 1, pageSize: 50 });
    });
});
