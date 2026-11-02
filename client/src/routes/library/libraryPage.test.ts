import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { TagGET } from "../../types/openapi_types";

const { goto, page } = vi.hoisted(() => ({
    goto: vi.fn(),
    page: { url: new URL("http://localhost/library") },
}));
vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$app/paths", () => ({ resolve: (route: string) => route }));
vi.mock("$app/state", () => ({ page }));
// Main needs the app context; a plain div wrapper stands in for it.
vi.mock(
    "$lib/components/Main.svelte",
    () => import("$lib/components/ui/table/table-toolbar.svelte"),
);
vi.mock("$lib/data/api", () => ({
    fetchTags: vi.fn(),
    fetchFeatures: vi.fn(),
}));

const { fetchTags, fetchFeatures } = await import("$lib/data/api");
const { tags } = await import("$lib/data/stores.svelte");
const { default: LibraryPage } = await import("./+page.svelte");

function renderPage(search: string) {
    page.url = new URL(`http://localhost/library${search}`);
    return render(LibraryPage, {
        context: new Map([
            ["globalContext", { makeInstancesBrowserURL: () => "/browser" }],
        ]),
    });
}

afterEach(() => {
    tags.clear();
    vi.clearAllMocks();
});

describe("/library", () => {
    it("shows only tags of the type in the URL", async () => {
        vi.mocked(fetchTags).mockResolvedValue([]);
        vi.mocked(fetchFeatures).mockResolvedValue([]);
        tags.set(1, {
            id: 1,
            name: "Blurry",
            tag_type: "ImageInstance",
        } as TagGET);
        tags.set(2, {
            id: 2,
            name: "Artefact",
            tag_type: "Segmentation",
        } as TagGET);

        renderPage("?type=Segmentation");

        expect(await screen.findByText("Artefact")).toBeInTheDocument();
        expect(screen.queryByText("Blurry")).toBeNull();
    });

    it("opens the tab in the URL and drops it from the URL when switching", async () => {
        vi.mocked(fetchTags).mockResolvedValue([]);
        vi.mocked(fetchFeatures).mockResolvedValue([]);

        renderPage("?tab=features");

        expect(screen.getByRole("tab", { name: "Features" })).toHaveAttribute(
            "aria-selected",
            "true",
        );
        await fireEvent.click(screen.getByRole("tab", { name: "Tags" }));
        expect(goto).toHaveBeenCalledWith("/library", {
            replaceState: true,
            keepFocus: true,
            noScroll: true,
        });
    });

    it("says when the tags could not be loaded", async () => {
        vi.mocked(fetchTags).mockRejectedValue(new Error("Forbidden"));
        vi.mocked(fetchFeatures).mockResolvedValue([]);

        renderPage("");

        expect(
            await screen.findByText("Tags could not be loaded"),
        ).toBeInTheDocument();
        expect(screen.getByText("Forbidden")).toBeInTheDocument();
    });
});
