import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";

vi.mock("svelte-sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
        message: vi.fn(),
    },
}));

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

const { updateSubTask } = await import("$lib/data/api");
const { toast } = await import("svelte-sonner");
const { default: SubtasksTable } = await import("./SubtasksTable.svelte");

function row(
    overrides: Partial<SubTaskWithImagesGET> = {},
): SubTaskWithImagesGET {
    return {
        id: 1,
        index: 0,
        task_id: 9,
        task_state: "todo",
        comments: "",
        images: [],
        creator: null,
        creator_id: null,
        ...overrides,
    } as SubTaskWithImagesGET;
}

describe("SubtasksTable", () => {
    beforeEach(() => {
        vi.mocked(updateSubTask).mockReset();
        vi.mocked(toast.success).mockClear();
        vi.mocked(toast.message).mockClear();
    });

    it("claims all unassigned rows on the page", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        const onAssignmentChange = vi.fn();
        render(SubtasksTable, {
            props: {
                rows: [
                    row({ id: 1 }),
                    row({
                        id: 2,
                        creator: { id: 5, name: "me" } as never,
                        creator_id: 5,
                    }),
                ],
                taskId: 9,
                count: 2,
                page: 0,
                onPageChange: vi.fn(),
                onAssignmentChange,
            },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        await fireEvent.click(
            screen.getByRole("button", {
                name: /Claim all unassigned on this page/,
            }),
        );
        expect(updateSubTask).toHaveBeenCalledTimes(1);
        expect(updateSubTask).toHaveBeenCalledWith(1, { claim: true });
        expect(toast.success).toHaveBeenCalled();
        expect(onAssignmentChange).toHaveBeenCalled();
    });

    it("reports mixed claim results", async () => {
        vi.mocked(updateSubTask).mockRejectedValue(new Error("fail"));
        render(SubtasksTable, {
            props: {
                rows: [row({ id: 1 }), row({ id: 2 })],
                taskId: 9,
                count: 2,
                page: 0,
                onPageChange: vi.fn(),
            },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        await fireEvent.click(
            screen.getByRole("button", {
                name: /Claim all unassigned on this page/,
            }),
        );
        expect(toast.message).toHaveBeenCalledWith("Claimed 0, failed 2");
    });

    it("shows an empty state", () => {
        render(SubtasksTable, {
            props: {
                rows: [],
                taskId: 9,
                count: 0,
                page: 0,
                onPageChange: vi.fn(),
            },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        expect(screen.getByText("No results.")).toBeInTheDocument();
        expect(
            screen.getByRole("button", {
                name: /Claim all unassigned on this page/,
            }),
        ).toBeDisabled();
    });
});
