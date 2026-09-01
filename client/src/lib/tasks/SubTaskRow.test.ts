import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { ApiError } from "$lib/api/client";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";

// The picker is the only route into confirmImages, and the real one mounts the
// whole search UI. Stand in for it and keep the callback it was handed.
const { pickerProps } = vi.hoisted(() => ({
    pickerProps: [] as { onConfirm: (ids: string[]) => Promise<void> }[],
}));

vi.mock("$lib/browser/BrowserPicker.svelte", () => ({
    default: (
        _anchor: unknown,
        props: { onConfirm: (ids: string[]) => Promise<void> },
    ) => {
        pickerProps.push(props);
    },
}));

vi.mock("$lib/browser/InstanceComponent.svelte", () => ({
    default: {
        name: "InstanceComponent",
        render: () => ({ $$slots: {}, $$events: {} }),
    },
}));

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

const { updateSubTask } = await import("$lib/data/api");
const { addSubTaskImage } = await import("$lib/data/helpers");
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

// The row reads the signed-in user out of context to decide whose claim it is.
function renderRow(props: Record<string, unknown>) {
    return render(SubTaskRow, {
        props,
        context: new Map([["globalContext", { user: { id: 5 } }]]),
    } as never);
}

beforeEach(() => {
    pickerProps.length = 0;
    vi.mocked(updateSubTask).mockReset();
    vi.mocked(addSubTaskImage).mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
});

describe("SubTaskRow", () => {
    it("claims an unassigned subtask", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        const onAssignmentChange = vi.fn();
        renderRow({ subtask: makeRow(), taskId: 9, onAssignmentChange });

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        expect(updateSubTask).toHaveBeenCalledWith(11, { claim: true });
        expect(toast.success).toHaveBeenCalledWith("Subtask claimed");
        expect(onAssignmentChange).toHaveBeenCalled();
    });

    it("unclaims a subtask assigned to the current user", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        renderRow({
            subtask: makeRow({
                creator: { id: 5, name: "me" } as never,
                creator_id: 5,
            }),
            taskId: 9,
        });

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
        renderRow({ subtask: makeRow(), taskId: 9, onAssignmentChange });

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        expect(toast.error).toHaveBeenCalledWith("SubTask is already assigned");
        expect(onAssignmentChange).toHaveBeenCalled();
    });
});

const REFUSED_ID = "88213";

const refusal = new ApiError(409, "conflict", {
    code: "image_outside_task_declaration",
    message: "Image 88213 is in a project this task does not declare.",
    image_projects: [17],
    declared_projects: [4, 9],
});

// A subtask with no images yet, so confirming a selection is purely an add.
async function confirmSelection() {
    renderRow({ subtask: makeRow({ id: 31, index: 0 }), taskId: 7 });

    await fireEvent.click(
        screen.getByRole("button", { name: /Browse images/i }),
    );

    const props = pickerProps.at(-1);
    if (!props) throw new Error("the picker never mounted");
    await props.onConfirm([REFUSED_ID]);
}

describe("SubTaskRow image selection", () => {
    it("tells the grader which earlier changes were kept when one is refused", async () => {
        vi.mocked(addSubTaskImage).mockRejectedValue(refusal);

        await confirmSelection();

        expect(addSubTaskImage).toHaveBeenCalledWith(31, REFUSED_ID);
        expect(toast.error).toHaveBeenCalledWith(
            "Image 88213 is in a project this task does not declare.",
            {
                description:
                    "Image project 17; task declares 4, 9. " +
                    "Earlier changes were saved; the rest were not applied.",
            },
        );
    });

    it("reports a failure that is not the declaration refusal", async () => {
        vi.mocked(addSubTaskImage).mockRejectedValue(new Error("Network down"));

        await confirmSelection();

        // One argument, not two: the refusal's description names projects the
        // server never sent for this error.
        expect(toast.error).toHaveBeenCalledWith("Error: Network down");
    });
});
