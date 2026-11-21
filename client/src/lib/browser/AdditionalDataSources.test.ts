import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyGET } from "../../types/openapi_types";

const fetchApi = vi.hoisted(() => vi.fn());
vi.mock("$lib/api/client", () => ({ fetchApi }));

import AdditionalDataSources from "./AdditionalDataSources.svelte";
import { loadDataSource } from "./dataSources";

function json(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status });
}

function study(
    id: number,
    data_sources: { name: string; collapse: boolean }[],
): StudyGET {
    return { id, data_sources } as unknown as StudyGET;
}

describe("AdditionalDataSources", () => {
    beforeEach(() => {
        fetchApi.mockReset();
    });

    it("takes the sources from the study and loads each one without a list request", async () => {
        fetchApi.mockResolvedValue(json({ "Table A": [["x", 1]] }));

        render(AdditionalDataSources, {
            props: {
                study: study(7, [
                    { name: "Registry", collapse: false },
                    { name: "Folded", collapse: true },
                ]),
            },
        });

        expect(
            await screen.findByRole("button", { name: "Table A" }),
        ).toBeTruthy();
        expect(
            screen
                .getByRole("button", { name: "Registry" })
                .getAttribute("aria-expanded"),
        ).toBe("true");
        expect(
            screen
                .getByRole("button", { name: "Folded" })
                .getAttribute("aria-expanded"),
        ).toBe("false");
        expect(fetchApi.mock.calls.map((c) => c[0])).not.toContain(
            "/studies/7/data-sources",
        );
        expect(fetchApi).toHaveBeenCalledWith(
            "/studies/7/data-sources/Registry",
        );
    });

    it("keeps the panels the user opened or closed when the study object is replaced", async () => {
        fetchApi.mockResolvedValue(json({ "Table A": [["x", 1]] }));
        const sources = [
            { name: "Registry", collapse: false },
            { name: "Folded", collapse: true },
        ];
        const { rerender } = render(AdditionalDataSources, {
            props: { study: study(12, sources) },
        });
        const expanded = (name: string) =>
            screen.getByRole("button", { name }).getAttribute("aria-expanded");

        await fireEvent.click(screen.getByRole("button", { name: "Registry" }));
        await fireEvent.click(screen.getByRole("button", { name: "Folded" }));
        expect(expanded("Registry")).toBe("false");
        expect(expanded("Folded")).toBe("true");

        await rerender({ study: study(12, sources) });

        expect(expanded("Registry")).toBe("false");
        expect(expanded("Folded")).toBe("true");
    });

    it("shows nothing when the study has no sources", () => {
        const { container } = render(AdditionalDataSources, {
            props: { study: study(8, []) },
        });

        expect(fetchApi).not.toHaveBeenCalled();
        expect(container.textContent?.trim()).toBe("");
    });

    it("keeps the page up when one source fails", async () => {
        fetchApi.mockResolvedValue(json({ detail: "x" }, 502));

        render(AdditionalDataSources, {
            props: { study: study(9, [{ name: "Broken", collapse: false }]) },
        });

        expect(
            await screen.findByText("Broken could not be loaded"),
        ).toBeTruthy();
    });

    it("says there is no data when the upstream returns 404", async () => {
        fetchApi.mockResolvedValue(json({ detail: "none" }, 404));

        render(AdditionalDataSources, {
            props: { study: study(10, [{ name: "Empty", collapse: false }]) },
        });

        expect(await screen.findByText("No data for this study.")).toBeTruthy();
        expect(screen.queryByText("Empty could not be loaded")).toBeNull();
    });
});

describe("loadDataSource cache", () => {
    beforeEach(() => {
        fetchApi.mockReset();
    });

    it("retries after a failed fetch and reuses a successful one", async () => {
        fetchApi
            .mockResolvedValueOnce(json({ detail: "x" }, 502))
            .mockResolvedValueOnce(json({ T: [[1]] }));

        await expect(loadDataSource(11, "Flaky")).rejects.toThrow();
        expect(await loadDataSource(11, "Flaky")).toEqual({ T: [[1]] });
        expect(await loadDataSource(11, "Flaky")).toEqual({ T: [[1]] });
        expect(fetchApi).toHaveBeenCalledTimes(2);
    });
});
