import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const loadDataSource = vi.hoisted(() => vi.fn());
vi.mock("$lib/browser/dataSources", async () => ({
    ...(await vi.importActual<object>("$lib/browser/dataSources")),
    loadDataSource,
}));

import AdditionalDataSources from "./AdditionalDataSources.svelte";

const sources = [
    {
        name: "Registry",
        url: "/registry/${study.id}",
        conditions: [],
    },
];

describe("AdditionalDataSources", () => {
    beforeEach(() => {
        loadDataSource.mockReset();
        loadDataSource.mockResolvedValue({ "Table A": [["x", 1]] });
    });

    it("does not reload when the context changes but the URL does not", async () => {
        const { rerender } = render(AdditionalDataSources, {
            props: {
                context: { study: { id: 7, tags: [] } },
                additional_data_sources: sources,
            },
        });
        await screen.findByRole("button", { name: "Table A" });
        expect(loadDataSource).toHaveBeenCalledTimes(1);

        await rerender({
            context: { study: { id: 7, tags: [{ id: 1 }] } },
            additional_data_sources: sources,
        });

        expect(screen.queryByText("Loading…")).toBeNull();
        expect(screen.getByRole("button", { name: "Table A" })).toBeTruthy();
        expect(loadDataSource).toHaveBeenCalledTimes(1);
    });
});
