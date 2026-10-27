import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import { formSchemas, instances } from "$lib/data/stores.svelte";
import type {
    FormSchemaGET,
    ImageGET,
    StudyGET,
} from "../../types/openapi_types";

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));

vi.mock("$lib/extensions", () => ({
    default: {
        browser: {
            study: {
                list_forms: [
                    {
                        title: "Visit grades",
                        schema_name: "Visit grades",
                        split_laterality: false,
                        create_new: false,
                    },
                ],
                additional_data_sources: [
                    {
                        name: "External grades",
                        url: "/external",
                        conditions: [],
                    },
                ],
            },
        },
    },
}));

vi.mock("$lib/data", async (importOriginal) => {
    const actual = await importOriginal<typeof import("$lib/data")>();
    return {
        ...actual,
        fetchFormAnnotations: vi.fn(async () => []),
    };
});

vi.mock("$lib/browser/dataSources", async (importOriginal) => {
    const actual =
        await importOriginal<typeof import("$lib/browser/dataSources")>();
    return {
        ...actual,
        loadDataSource: vi.fn(async () => ({ Scores: [] })),
    };
});

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

beforeEach(() => {
    formSchemas.clear();
    formSchemas.set(1, { id: 1, name: "Visit grades" } as FormSchemaGET);
});

describe("StudyBlock", () => {
    it("shows visit grading and the data sources", async () => {
        renderStudy();
        expect(
            await screen.findByRole("heading", { name: "Visit grades" }),
        ).toBeInTheDocument();
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
