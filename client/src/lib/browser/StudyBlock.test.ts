import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { formSchemas } from "$lib/data/stores.svelte";
import type { FormSchemaGET, StudyGET } from "../../types/openapi_types";

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
]);

function renderBlock(mode: "full" | "overlay") {
    return render(StudyBlock, { props: { study, mode }, context });
}

describe("StudyBlock grading", () => {
    beforeEach(() => {
        formSchemas.clear();
        formSchemas.set(1, {
            id: 1,
            name: "Visit grades",
        } as FormSchemaGET);
    });

    it("shows visit grading in the study browser", async () => {
        renderBlock("full");
        expect(
            await screen.findByRole("heading", { name: "Visit grades" }),
        ).toBeInTheDocument();
        expect(
            await screen.findByRole("heading", { name: /External grades/ }),
        ).toBeInTheDocument();
    });

    it("keeps visit grading collapsed in the viewer browse popup", async () => {
        renderBlock("overlay");
        expect(
            screen.queryByRole("heading", { name: "Visit grades" }),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("heading", { name: /External grades/ }),
        ).not.toBeInTheDocument();

        await fireEvent.click(screen.getByRole("button", { name: /Grading/ }));

        expect(
            await screen.findByRole("heading", { name: "Visit grades" }),
        ).toBeInTheDocument();
        await waitFor(() => {
            expect(
                screen.getByRole("heading", { name: /External grades/ }),
            ).toBeInTheDocument();
        });
    });
});
