import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import type { FeatureGET } from "../../types/openapi_types";

vi.mock("$lib/data/helpers", () => ({
    createFeature: vi.fn(),
    updateFeature: vi.fn(),
    deleteFeature: vi.fn(),
}));
vi.mock("$lib/data/api", () => ({ fetchFeatures: vi.fn() }));

const { createFeature, updateFeature, deleteFeature } = await import(
    "$lib/data/helpers"
);
const { fetchFeatures } = await import("$lib/data/api");
const { ApiError } = await import("$lib/api/client");
const { features } = await import("$lib/data/stores.svelte");
const { default: FeaturesTable } = await import("./FeaturesTable.svelte");

function feature(
    id: number,
    name: string,
    extra: Partial<FeatureGET> = {},
): FeatureGET {
    return {
        id,
        name,
        subfeatures: [],
        subfeature_ids: [],
        segmentation_count: 0,
        ...extra,
    } as unknown as FeatureGET;
}

function renderTable() {
    return render(FeaturesTable, {
        context: new Map([
            [
                "globalContext",
                { makeInstancesBrowserURL: () => "/browser?q=1" },
            ],
        ]),
    });
}

async function openDelete(name: string) {
    await fireEvent.click(
        screen.getByRole("button", { name: `Delete ${name}` }),
    );
    const dialog = await screen.findByRole("dialog");
    await fireEvent.click(
        within(dialog).getByRole("button", { name: "Delete" }),
    );
    return dialog;
}

beforeEach(() => {
    vi.mocked(fetchFeatures).mockResolvedValue([]);
    features.set(2, feature(2, "Drusen", { segmentation_count: 3 }));
    features.set(
        1,
        feature(1, "AMD", {
            subfeatures: [{ index: 0, name: "Drusen" }],
            subfeature_ids: [2],
        }),
    );
});

afterEach(() => {
    features.clear();
    vi.clearAllMocks();
});

describe("FeaturesTable", () => {
    it("lists features by name with subfeatures and counts, and filters on search", async () => {
        renderTable();

        const cells = within(screen.getByRole("table", { name: "Features" }))
            .getAllByRole("row")
            .slice(1)
            .map((row) =>
                within(row)
                    .getAllByRole("cell")
                    .slice(0, 3)
                    .map((c) => c.textContent?.trim()),
            );
        expect(cells).toEqual([
            ["AMD", "Drusen", "0"],
            ["Drusen", "—", "3"],
        ]);

        await fireEvent.input(screen.getByLabelText("Search features"), {
            target: { value: "xyz" },
        });
        expect(screen.getByText("No features match “xyz”")).toBeInTheDocument();
    });

    it("requires a name, then creates with the trimmed name and reloads counts", async () => {
        vi.mocked(createFeature).mockResolvedValue(
            feature(3, "Atrophy") as never,
        );
        renderTable();

        await fireEvent.click(
            screen.getByRole("button", { name: /Create feature/ }),
        );
        const dialog = await screen.findByRole("dialog");
        const submit = within(dialog).getByRole("button", {
            name: "Create feature",
        });

        await fireEvent.click(submit);
        expect(createFeature).not.toHaveBeenCalled();
        expect(
            within(dialog).getByText("Enter a feature name"),
        ).toBeInTheDocument();

        await fireEvent.input(within(dialog).getByLabelText("Name"), {
            target: { value: "  Atrophy " },
        });
        await fireEvent.click(submit);

        await waitFor(() =>
            expect(fetchFeatures).toHaveBeenCalledWith({ with_counts: true }),
        );
        expect(createFeature).toHaveBeenCalledWith({
            name: "Atrophy",
            subfeature_ids: [],
        });
    });

    it("saves an edit with the feature's existing subfeatures", async () => {
        vi.mocked(updateFeature).mockResolvedValue(feature(1, "AMD") as never);
        renderTable();

        await fireEvent.click(screen.getByRole("button", { name: "Edit AMD" }));
        const dialog = await screen.findByRole("dialog");
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Save" }),
        );

        await waitFor(() =>
            expect(updateFeature).toHaveBeenCalledWith(1, {
                name: "AMD",
                subfeature_ids: [2],
            }),
        );
    });

    it.each([
        {
            name: "Drusen",
            detail: { code: "FEATURE_HAS_SEGMENTATIONS" },
            shown: "Used by 3 segmentations in your projects. Remove those first.",
        },
        {
            name: "AMD",
            detail: { code: "FEATURE_HAS_SEGMENTATIONS" },
            shown: "This feature is used by segmentations in projects you don't have access to, so it can't be deleted.",
        },
        {
            name: "Drusen",
            detail: { code: "FEATURE_IS_CHILD", parents: ["AMD", "GA"] },
            shown: "Feature is a subfeature. Parent features: AMD, GA.",
        },
    ])(
        "words the $detail.code refusal for $name",
        async ({ name, detail, shown }) => {
            vi.mocked(deleteFeature).mockRejectedValue(
                new ApiError(409, "Feature is a subfeature.", detail),
            );
            renderTable();

            const dialog = await openDelete(name);

            expect(await within(dialog).findByRole("alert")).toHaveTextContent(
                shown,
            );
        },
    );

    it("moves focus to the page heading after deleting a feature", async () => {
        vi.mocked(deleteFeature).mockImplementation(async (id: number) => {
            features.delete(id);
        });
        const heading = document.createElement("h1");
        heading.id = "library-heading";
        heading.tabIndex = -1;
        document.body.append(heading);
        renderTable();

        await openDelete("Drusen");

        // The modal closes after its 1.5 s success state.
        await waitFor(() => expect(heading).toHaveFocus(), { timeout: 3000 });
        expect(
            screen.queryByRole("button", { name: "Delete Drusen" }),
        ).toBeNull();
        heading.remove();
    });
});
