import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import { instances } from "$lib/data/stores.svelte";
import type { ImageGET, StudyGET } from "../../types/openapi_types";

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));

vi.mock("$lib/browser/dataSources", () => ({
    listDataSources: vi.fn(async () => [
        { name: "External grades", collapse: false },
    ]),
    loadDataSource: vi.fn(async () => ({ Scores: [] })),
}));

const { default: StudyBlock } = await import("./StudyBlock.svelte");

const study = {
    id: 42,
    date: "2020-01-01",
    patient: { id: 1, identifier: "P1", sex: "M" },
    project: { name: "Test" },
    series: [],
    tags: [],
} as unknown as StudyGET;

const context = new Map<string, unknown>([
    ["globalContext", { makeStudiesBrowserURL: () => "/studies" }],
    [
        "browserContext",
        { selectedIds: [], thumbnailSize: "8rem", toggleInstance: vi.fn() },
    ],
]);

const image = (id: string, laterality: "L" | "R" | null) =>
    ({ id, laterality, tags: [] }) as unknown as ImageGET;

function renderStudy(images: ImageGET[] = []) {
    instances.clear();
    for (const i of images) instances.set(i.id, i);
    const withSeries = {
        ...study,
        series: [{ id: 1, instance_ids: images.map((i) => i.id) }],
    } as unknown as StudyGET;
    return render(StudyBlock, { props: { study: withSeries }, context });
}

describe("StudyBlock", () => {
    it("shows the data sources", async () => {
        renderStudy();
        expect(
            await screen.findByRole("heading", { name: /External grades/ }),
        ).toBeInTheDocument();
    });

    it("shows the unknown-laterality column only when it has images", () => {
        const { unmount } = renderStudy([image("a", "R")]);
        expect(
            screen.queryByRole("heading", { name: "Laterality unknown" }),
        ).toBeNull();
        unmount();

        renderStudy([image("a", "R"), image("b", null)]);
        expect(
            screen.getByRole("heading", { name: "Laterality unknown" }),
        ).toBeInTheDocument();
    });

    it("links each eye's images to the viewer", () => {
        renderStudy([image("a", "R"), image("b", "L"), image("c", "R")]);
        expect(
            screen
                .getByRole("link", { name: "Open all OD images" })
                .getAttribute("href"),
        ).toBe("/view?instances=a,c");
    });
});
