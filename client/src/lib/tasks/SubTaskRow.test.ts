import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { ApiError } from "$lib/api/client";
import { addSubTaskImage } from "$lib/data/helpers";
import { toast } from "svelte-sonner";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";
import SubTaskRow from "./SubTaskRow.svelte";

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

vi.mock("$lib/data/helpers", () => ({
    addSubTaskImage: vi.fn(),
    removeSubTaskImage: vi.fn(),
    updateSubTaskComments: vi.fn(),
}));

vi.mock("svelte-sonner", () => ({ toast: { error: vi.fn() } }));

const REFUSED_ID = "88213";

const refusal = new ApiError(409, "conflict", {
    code: "image_outside_task_declaration",
    message: "Image 88213 is in a project this task does not declare.",
    image_projects: [17],
    declared_projects: [4, 9],
});

// A subtask with no images yet, so confirming a selection is purely an add.
const subtask = {
    id: 31,
    index: 0,
    images: [],
} as unknown as SubTaskWithImagesGET;

async function confirmSelection() {
    render(SubTaskRow, { props: { subtask, taskId: 7 } });

    await fireEvent.click(
        screen.getByRole("button", { name: /Browse images/i }),
    );

    const props = pickerProps.at(-1);
    if (!props) throw new Error("the picker never mounted");
    await props.onConfirm([REFUSED_ID]);
}

describe("SubTaskRow image selection", () => {
    beforeEach(() => {
        pickerProps.length = 0;
    });

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
