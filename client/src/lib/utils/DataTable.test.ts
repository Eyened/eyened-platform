import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import DataTable from "./DataTable.svelte";

describe("DataTable", () => {
    it("shows markup in a cell as text", () => {
        const { container } = render(DataTable, {
            props: { tag: "Source", data: [[1, "<b>x</b>", null, null]] },
        });
        expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
        expect(container.querySelector("b")).toBeNull();
    });
});
