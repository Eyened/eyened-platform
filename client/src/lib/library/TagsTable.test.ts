import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import type { TagGET } from "../../types/openapi_types";

vi.mock("$lib/data/helpers", () => ({
    createTag: vi.fn(),
    deleteTag: vi.fn(),
}));

const { createTag, deleteTag } = await import("$lib/data/helpers");
const { tags } = await import("$lib/data/stores.svelte");
const { default: TagsTable } = await import("./TagsTable.svelte");

function tag(
    id: number,
    name: string,
    tag_type: string,
    extra: Partial<TagGET> = {},
): TagGET {
    return { id, name, tag_type, description: "", ...extra } as TagGET;
}

function renderTable(type = "all") {
    return render(TagsTable, { props: { type, onselecttype: vi.fn() } });
}

function cellText(row: HTMLElement) {
    return within(row)
        .getAllByRole("cell")
        .slice(0, 4)
        .map((c) => c.textContent?.trim());
}

function bodyRows() {
    return within(screen.getByRole("table", { name: "Tags" }))
        .getAllByRole("row")
        .slice(1);
}

beforeEach(() => {
    tags.set(
        1,
        tag(1, "Blurry", "ImageInstance", {
            description: "Out of focus",
            creator: { id: 7, name: "jdoe" },
        } as Partial<TagGET>),
    );
    tags.set(2, tag(2, "Artefact", "Segmentation"));
});

afterEach(() => {
    tags.clear();
    vi.clearAllMocks();
});

describe("TagsTable", () => {
    it("lists tags by name with type label and owner", () => {
        renderTable();

        expect(bodyRows().map(cellText)).toEqual([
            ["Artefact", "—", "Segmentation", "—"],
            ["Blurry", "Out of focus", "Image", "jdoe"],
        ]);
    });

    it("filters by type and searches name and description", async () => {
        renderTable("ImageInstance");
        expect(bodyRows()).toHaveLength(1);

        await fireEvent.input(screen.getByLabelText("Search tags"), {
            target: { value: "focus" },
        });
        expect(bodyRows()[0]).toHaveTextContent("Blurry");

        await fireEvent.input(screen.getByLabelText("Search tags"), {
            target: { value: "artefact" },
        });
        expect(
            screen.getByText("No tags match “artefact”"),
        ).toBeInTheDocument();
    });

    it("says when no tag has the chosen type", () => {
        renderTable("FormAnnotation");

        expect(screen.getByText("No tags of this type")).toBeInTheDocument();
    });

    it("requires a name, then creates the tag with the filtered type", async () => {
        vi.mocked(createTag).mockResolvedValue(undefined as never);
        renderTable("Segmentation");

        await fireEvent.click(
            screen.getByRole("button", { name: /Create tag/ }),
        );
        const dialog = await screen.findByRole("dialog");
        const submit = within(dialog).getByRole("button", {
            name: "Create tag",
        });

        await fireEvent.click(submit);
        expect(createTag).not.toHaveBeenCalled();
        expect(
            within(dialog).getByText("Enter a tag name"),
        ).toBeInTheDocument();

        await fireEvent.input(within(dialog).getByLabelText("Name"), {
            target: { value: " Noise " },
        });
        await fireEvent.input(
            within(dialog).getByLabelText("Description (optional)"),
            { target: { value: "Speckle" } },
        );
        await fireEvent.click(submit);

        await waitFor(() =>
            expect(createTag).toHaveBeenCalledWith(
                "Noise",
                "Segmentation",
                "Speckle",
            ),
        );
    });

    it("deletes a tag only after the confirm", async () => {
        vi.mocked(deleteTag).mockResolvedValue(undefined as never);
        renderTable();

        await fireEvent.click(
            screen.getByRole("button", { name: "Delete Blurry" }),
        );
        const dialog = await screen.findByRole("dialog");
        expect(deleteTag).not.toHaveBeenCalled();

        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await waitFor(() => expect(deleteTag).toHaveBeenCalledWith(1));
    });
});
