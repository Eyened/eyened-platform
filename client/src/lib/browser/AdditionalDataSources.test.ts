import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchApi = vi.hoisted(() => vi.fn());
vi.mock("$lib/api/client", () => ({ fetchApi }));

import AdditionalDataSources from "./AdditionalDataSources.svelte";

function json(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status });
}

describe("AdditionalDataSources", () => {
    beforeEach(() => {
        fetchApi.mockReset();
    });

    it("lists the server's sources for the study and loads each one", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/7/data-sources"
                ? json([
                      { name: "Registry", collapse: false },
                      { name: "Folded", collapse: true },
                  ])
                : json({ "Table A": [["x", 1]] }),
        );

        render(AdditionalDataSources, { props: { studyId: 7 } });

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
        expect(fetchApi).toHaveBeenCalledWith(
            "/studies/7/data-sources/Registry",
        );
    });

    it("shows nothing when no source applies", async () => {
        fetchApi.mockResolvedValue(json([]));

        const { container } = render(AdditionalDataSources, {
            props: { studyId: 8 },
        });
        await vi.waitFor(() => expect(fetchApi).toHaveBeenCalledOnce());

        expect(container.textContent?.trim()).toBe("");
    });

    it("keeps the page up when one source fails", async () => {
        fetchApi.mockImplementation(async (path: string) =>
            path === "/studies/9/data-sources"
                ? json([{ name: "Broken", collapse: false }])
                : json({ detail: "x" }, 502),
        );

        render(AdditionalDataSources, { props: { studyId: 9 } });

        expect(
            await screen.findByText("Broken could not be loaded"),
        ).toBeTruthy();
    });
});
