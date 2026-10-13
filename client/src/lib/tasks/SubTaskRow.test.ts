import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { ApiError } from "$lib/api/client";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";

// The picker is the only route into confirmImages, and the real one mounts the
// whole search UI. Stand in for it and keep the callback it was handed.
const { pickerProps } = vi.hoisted(() => ({
    pickerProps: [] as { onConfirm: (ids: string[]) => Promise<void> }[],
}));

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));

vi.mock("$lib/browser/BrowserPicker.svelte", () => ({
    default: (
        _anchor: unknown,
        props: { onConfirm: (ids: string[]) => Promise<void> },
    ) => {
        pickerProps.push(props);
    },
}));

vi.mock("$lib/browser/InstanceComponent.svelte", () => ({
    default: () => null,
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
const { default: SubTaskRow } = await import("./SubTaskRow.svelte");

function makeRow(
    overrides: Partial<SubTaskWithImagesGET> = {},
): SubTaskWithImagesGET {
    return {
        id: 11,
        index: 2,
        task_id: 9,
        task_state: "NotStarted",
        comments: "",
        images: [],
        creator: null,
        creator_id: null,
        ...overrides,
    } as SubTaskWithImagesGET;
}

// The row reads the signed-in user out of context to decide whose claim it is.
function renderRow(props: Record<string, unknown>) {
    const callbacks = {
        ontoggle: vi.fn(),
        onedit: vi.fn(),
        onerror: vi.fn(),
        onchange: vi.fn(),
    };
    const { rerender } = render(SubTaskRow, {
        props: {
            taskId: 9,
            headingId: "task-heading",
            expanded: false,
            ...callbacks,
            ...props,
        },
        context: new Map([["globalContext", { user: { id: 5 } }]]),
    } as never);
    return { ...callbacks, rerender };
}

beforeEach(() => {
    pickerProps.length = 0;
    vi.mocked(updateSubTask).mockReset();
    vi.mocked(addSubTaskImage).mockReset();
});

describe("SubTaskRow", () => {
    it("claims an unassigned set, then refreshes", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        const { onchange } = renderRow({ subtask: makeRow() });

        await fireEvent.click(
            screen.getByRole("button", { name: "Claim set 2" }),
        );
        expect(updateSubTask).toHaveBeenCalledWith(11, { claim: true });
        expect(onchange).toHaveBeenCalled();
    });

    it("unclaims a set assigned to the current user", async () => {
        vi.mocked(updateSubTask).mockResolvedValue({});
        renderRow({
            subtask: makeRow({
                creator: { id: 5, name: "me" } as never,
                creator_id: 5,
            }),
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Unclaim set 2" }),
        );
        expect(updateSubTask).toHaveBeenCalledWith(11, { claim: false });
    });

    it("reports a failed claim", async () => {
        vi.mocked(updateSubTask).mockRejectedValue(
            new ApiError(409, "SubTask is already assigned", {
                code: "subtask_already_claimed",
            }),
        );
        const { onerror, onchange } = renderRow({ subtask: makeRow() });

        await fireEvent.click(
            screen.getByRole("button", { name: "Claim set 2" }),
        );
        expect(onerror).toHaveBeenCalledWith(
            "Set 2 could not be claimed",
            "SubTask is already assigned",
        );
        expect(onchange).not.toHaveBeenCalled();
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
async function openPicker() {
    const rendered = renderRow({
        subtask: makeRow({ id: 31, index: 0 }),
        taskId: 7,
        expanded: true,
    });
    await fireEvent.click(
        screen.getByRole("button", { name: "Browse images" }),
    );
    const props = pickerProps.at(-1);
    if (!props) throw new Error("the picker never mounted");
    return { ...rendered, props };
}

describe("SubTaskRow image selection", () => {
    it("keeps the picker open and says which changes were kept when an image is refused", async () => {
        vi.mocked(addSubTaskImage).mockRejectedValue(refusal);
        const { props, onchange, onerror } = await openPicker();

        await expect(props.onConfirm([REFUSED_ID])).rejects.toThrow(
            "Image 88213 is in a project this task does not declare. " +
                "Image project 17; task declares 4, 9. " +
                "Earlier changes were saved; the rest were not applied.",
        );
        expect(onchange).toHaveBeenCalled();
        expect(onerror).not.toHaveBeenCalled();
    });

    it("refreshes after a failed save, so a retry sends only what was not saved", async () => {
        const { props, onchange, rerender } = await openPicker();
        onchange.mockImplementation(() =>
            rerender({
                subtask: makeRow({
                    id: 31,
                    index: 0,
                    images: [{ id: 1 }] as never,
                }),
            }),
        );
        vi.mocked(addSubTaskImage)
            .mockResolvedValueOnce(undefined)
            .mockRejectedValueOnce(new Error("Network down"));

        await expect(props.onConfirm(["1", "2"])).rejects.toThrow(
            "Network down",
        );

        vi.mocked(addSubTaskImage).mockReset().mockResolvedValue(undefined);
        await props.onConfirm(["1", "2"]);
        expect(addSubTaskImage).toHaveBeenCalledTimes(1);
        expect(addSubTaskImage).toHaveBeenCalledWith(31, "2");
    });
});
