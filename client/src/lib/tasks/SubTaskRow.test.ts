import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";
import { ApiError } from "$lib/api/client";

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
    default: {
        name: "BrowserPicker",
        render: () => ({ $$slots: {}, $$events: {} }),
    },
}));

vi.mock("$lib/browser/InstanceComponent.svelte", () => ({
    default: {
        name: "InstanceComponent",
        render: () => ({ $$slots: {}, $$events: {} }),
    },
}));

const { updateSubTask } = await import("$lib/data/api");
const { toast } = await import("svelte-sonner");
const { default: SubTaskRow } = await import("./SubTaskRow.svelte");

function makeRow(
    overrides: Partial<SubTaskWithImagesGET> = {},
): SubTaskWithImagesGET {
    return {
        id: 11,
        index: 2,
        task_id: 9,
        task_state: "todo",
        comments: "",
        images: [],
        creator: null,
        creator_id: null,
        ...overrides,
    } as SubTaskWithImagesGET;
}

describe("SubTaskRow", () => {
    beforeEach(() => {
        vi.mocked(updateSubTask).mockReset();
        vi.mocked(toast.success).mockClear();
        vi.mocked(toast.error).mockClear();
    });

    it("claims an unassigned subtask", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        const onAssignmentChange = vi.fn();
        render(SubTaskRow, {
            props: {
                subtask: makeRow(),
                taskId: 9,
                onAssignmentChange,
            },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        expect(updateSubTask).toHaveBeenCalledWith(11, { claim: true });
        expect(toast.success).toHaveBeenCalledWith("Subtask claimed");
        expect(onAssignmentChange).toHaveBeenCalled();
    });

    it("unclaims a subtask assigned to the current user", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        render(SubTaskRow, {
            props: {
                subtask: makeRow({
                    creator: { id: 5, name: "me" } as never,
                    creator_id: 5,
                }),
                taskId: 9,
            },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        expect(screen.getByText("me")).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("button", { name: "Unclaim" }));
        expect(updateSubTask).toHaveBeenCalledWith(11, { claim: false });
        expect(toast.success).toHaveBeenCalledWith("Subtask unclaimed");
    });

    it("toasts and refreshes when claim fails", async () => {
        vi.mocked(updateSubTask).mockRejectedValue(
            new ApiError(409, "SubTask is already assigned", {
                code: "subtask_already_claimed",
            }),
        );
        const onAssignmentChange = vi.fn();
        render(SubTaskRow, {
            props: { subtask: makeRow(), taskId: 9, onAssignmentChange },
            context: new Map([["globalContext", { user: { id: 5 } }]]),
        } as never);

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        expect(toast.error).toHaveBeenCalledWith("SubTask is already assigned");
        expect(onAssignmentChange).toHaveBeenCalled();
    });
});
