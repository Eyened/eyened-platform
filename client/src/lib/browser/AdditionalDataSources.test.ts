import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OPEN_EXTENSIONS_STORAGE_KEY } from "./openExtensionPrefs";

const fetchApi = vi.hoisted(() => vi.fn());
vi.mock("$lib/api/client", () => ({ fetchApi }));

import AdditionalDataSources from "./AdditionalDataSources.svelte";

function json(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status });
}

describe("AdditionalDataSources", () => {
    beforeEach(() => {
        fetchApi.mockReset();
        localStorage.clear();
    });

    it("lists the server's sources for the study and loads each one", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/7/data-sources"
                ? json([{ name: "Registry" }, { name: "Folded" }])
                : json({ kind: "tables", groups: { "Table A": [["x", 1]] } }),
        );

        render(AdditionalDataSources, { props: { studyId: 7 } });

        expect(
            await screen.findAllByRole("button", { name: "Table A" }),
        ).toHaveLength(2);
        expect(
            screen
                .getByRole("button", { name: "Registry" })
                .getAttribute("aria-expanded"),
        ).toBe("true");
        expect(
            screen
                .getByRole("button", { name: "Folded" })
                .getAttribute("aria-expanded"),
        ).toBe("true");
        expect(fetchApi).toHaveBeenCalledWith(
            "/studies/7/data-sources/Registry",
        );
        expect(localStorage.getItem(OPEN_EXTENSIONS_STORAGE_KEY)).toBe(
            JSON.stringify(["Registry", "Folded"]),
        );

        await fireEvent.click(screen.getByRole("button", { name: "Registry" }));

        await vi.waitFor(() => {
            expect(localStorage.getItem(OPEN_EXTENSIONS_STORAGE_KEY)).toBe(
                JSON.stringify(["Folded"]),
            );
        });
    });

    it("restores the open set from localStorage", async () => {
        localStorage.setItem(
            OPEN_EXTENSIONS_STORAGE_KEY,
            JSON.stringify(["Folded"]),
        );
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/7/data-sources"
                ? json([{ name: "Registry" }, { name: "Folded" }])
                : json({ kind: "tables", groups: { "Table A": [["x", 1]] } }),
        );

        render(AdditionalDataSources, { props: { studyId: 7 } });

        await screen.findByRole("button", { name: "Table A" });
        expect(
            screen
                .getByRole("button", { name: "Registry" })
                .getAttribute("aria-expanded"),
        ).toBe("false");
        expect(
            screen
                .getByRole("button", { name: "Folded" })
                .getAttribute("aria-expanded"),
        ).toBe("true");
    });

    it("shows nothing when no source applies", async () => {
        fetchApi.mockResolvedValue(json([]));

        const { container } = render(AdditionalDataSources, {
            props: { studyId: 8 },
        });
        await vi.waitFor(() => expect(fetchApi).toHaveBeenCalledOnce());

        expect(container.textContent?.trim()).toBe("");
    });

    it("shows no data when a source answers 404", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/11/data-sources"
                ? json([{ name: "Empty" }])
                : json({ detail: "none" }, 404),
        );

        render(AdditionalDataSources, { props: { studyId: 11 } });

        expect(await screen.findByText("No data for this study.")).toBeTruthy();
        expect(screen.queryByText("Empty could not be loaded")).toBeNull();
    });

    it("retries a source that failed", async () => {
        let loads = 0;
        fetchApi.mockImplementation(async (path: string) => {
            if (path === "/studies/12/data-sources") {
                return json([{ name: "Broken" }]);
            }
            loads += 1;
            return json({ detail: "x" }, 502);
        });

        const first = render(AdditionalDataSources, { props: { studyId: 12 } });
        expect(
            await screen.findByText("Broken could not be loaded"),
        ).toBeTruthy();
        first.unmount();

        render(AdditionalDataSources, { props: { studyId: 12 } });
        expect(
            await screen.findByText("Broken could not be loaded"),
        ).toBeTruthy();
        expect(loads).toBe(2);
    });

    it("keeps the page up when one source fails", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/9/data-sources"
                ? json([{ name: "Broken" }])
                : json({ detail: "x" }, 502),
        );

        render(AdditionalDataSources, { props: { studyId: 9 } });

        expect(
            await screen.findByText("Broken could not be loaded"),
        ).toBeTruthy();
    });

    it("keeps the page up when kind is not tables", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/10/data-sources"
                ? json([{ name: "Weird" }])
                : json({ kind: "markdown", body: "# hi" }),
        );

        render(AdditionalDataSources, { props: { studyId: 10 } });

        expect(
            await screen.findByText("Weird could not be loaded"),
        ).toBeTruthy();
    });
});
