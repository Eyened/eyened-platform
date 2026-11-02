import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { SvelteSet } from "svelte/reactivity";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));

vi.mock("$lib/data/api", () => ({
    updateSubTask: vi.fn(),
}));

vi.mock("$lib/data/helpers", () => ({
    addSubTaskImage: vi.fn(),
    removeSubTaskImage: vi.fn(),
    updateSubTaskComments: vi.fn(),
}));

vi.mock("$lib/browser/BrowserPicker.svelte", () => ({
    default: () => null,
}));

vi.mock("$lib/browser/InstanceComponent.svelte", () => ({
    default: () => null,
}));

vi.mock("$lib/browser/browserContext.svelte", () => ({
    BrowserContext: class BrowserContext {},
}));

const { updateSubTaskComments } = await import("$lib/data/helpers");
const { default: SubtasksTable } = await import("./SubtasksTable.svelte");

function row(
    overrides: Partial<SubTaskWithImagesGET> = {},
): SubTaskWithImagesGET {
    return {
        id: 1,
        index: 0,
        task_id: 9,
        task_state: "NotStarted",
        comments: "",
        images: [],
        creator: null,
        creator_id: null,
        ...overrides,
    } as SubTaskWithImagesGET;
}

function renderTable(rows: SubTaskWithImagesGET[]) {
    const onchange = vi.fn();
    render(SubtasksTable, {
        props: {
            rows,
            taskId: 9,
            headingId: "task-heading",
            expanded: new SvelteSet<number>(),
            onerror: vi.fn(),
            onchange,
        },
        context: new Map([["globalContext", { user: { id: 5 } }]]),
    } as never);
    return onchange;
}

const browseButtons = () =>
    screen.queryAllByRole("button", { name: "Browse images" });

describe("SubtasksTable", () => {
    it("expands every row, then collapses them all", async () => {
        renderTable([row({ id: 1, index: 0 }), row({ id: 2, index: 1 })]);

        await fireEvent.click(
            screen.getByRole("button", { name: "Expand all rows" }),
        );
        expect(browseButtons()).toHaveLength(2);

        await fireEvent.click(
            screen.getByRole("button", { name: "Collapse all rows" }),
        );
        expect(browseButtons()).toHaveLength(0);
    });

    it("refreshes after a comment save, which can assign the set", async () => {
        vi.mocked(updateSubTaskComments).mockResolvedValue({} as never);
        const onchange = renderTable([row({ id: 1, index: 0 })]);

        await fireEvent.click(
            screen.getByRole("button", { name: "Edit comments for set 0" }),
        );
        await fireEvent.input(
            await screen.findByRole("textbox", { name: "Comments" }),
            { target: { value: "Drusen" } },
        );
        await fireEvent.click(screen.getByRole("button", { name: "Save" }));

        await waitFor(() => expect(onchange).toHaveBeenCalled());
        expect(updateSubTaskComments).toHaveBeenCalledWith(1, "Drusen");
    });
});
