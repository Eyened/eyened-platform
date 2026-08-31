import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import TaskPanel from "./TaskPanel.svelte";
import type { TaskContext } from "./TaskContext.svelte";
import type { TaskGET, SubTaskWithImagesGET } from "../../types/openapi_types";
import { TASK_PANEL_EXPANDED_STORAGE_KEY } from "./taskPanelExpandedPrefs";
import { toast } from "svelte-sonner";

const updateSubTask = vi.fn().mockResolvedValue({});
const updateSubTaskComments = vi.fn().mockResolvedValue({});

vi.mock("$lib/data/api", () => ({
    updateSubTask: (...args: unknown[]) => updateSubTask(...args),
}));

vi.mock("$lib/data", () => ({
    updateSubTaskComments: (...args: unknown[]) =>
        updateSubTaskComments(...args),
}));

vi.mock("$app/state", () => ({
    page: { url: new URL("http://localhost/tasks/1/grade/0") },
}));

vi.mock("svelte-sonner", () => ({
    toast: { error: vi.fn() },
}));

function makeContext(
    config: unknown = {},
    overrides: Partial<TaskContext> = {},
): TaskContext {
    const task = {
        id: 42,
        name: "AMD",
        description: null,
        contact_id: null,
        task_definition_id: 1,
        date_inserted: "2026-01-01T00:00:00",
        num_tasks: 10,
        num_tasks_ready: 1,
        creator: null,
        task_state: null,
        task_definition: {
            id: 1,
            name: "Definition",
            config,
            date_inserted: "2026-01-01T00:00:00",
        },
        projects: null,
    } as TaskGET;
    const subTask = {
        id: 7,
        task_id: 42,
        task_index: 3,
        task_state: "NotStarted",
        comments: "hello",
        creator_id: null,
        images: [],
    } as unknown as SubTaskWithImagesGET;
    return { task, subTask, subTaskIndex: 3, ...overrides };
}

describe("TaskPanel", () => {
    beforeEach(() => {
        localStorage.clear();
        updateSubTask.mockClear();
        updateSubTaskComments.mockClear();
        updateSubTask.mockResolvedValue({});
        updateSubTaskComments.mockResolvedValue({});
        vi.mocked(toast.error).mockClear();
    });

    it("renders nothing when enabled is false", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({ task_panel: { enabled: false } }),
            },
        });
        expect(screen.queryByText("Set 3")).not.toBeInTheDocument();
    });

    it("shows collapsed chrome without comments or overview", () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        expect(screen.getByText("Set 3")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Previous subtask" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Next subtask" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "NotStarted", pressed: true }),
        ).toBeInTheDocument();
        expect(
            screen.queryByPlaceholderText("Add comments..."),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Task overview" }),
        ).not.toBeInTheDocument();
    });

    it("hides status when that section is off", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({
                    task_panel: { sections: { status: false } },
                }),
            },
        });
        expect(screen.getByText("Set 3")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "NotStarted" }),
        ).not.toBeInTheDocument();
    });

    it("hides the expand control when comments and overview are off", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({
                    task_panel: {
                        sections: { comments: false, overview: false },
                    },
                }),
            },
        });
        expect(screen.getByText("Set 3")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Expand task panel" }),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Collapse task panel" }),
        ).not.toBeInTheDocument();
    });

    it("reveals comments and overview when expanded", async () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        await fireEvent.click(
            screen.getByRole("button", { name: "Expand task panel" }),
        );
        expect(
            screen.getByPlaceholderText("Add comments..."),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Task overview" }),
        ).toBeInTheDocument();
        expect(
            JSON.parse(
                localStorage.getItem(TASK_PANEL_EXPANDED_STORAGE_KEY) ?? "{}",
            ),
        ).toEqual({ "42": true });
    });

    it("starts expanded when localStorage says so", () => {
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify({ "42": true }),
        );
        render(TaskPanel, { props: { taskContext: makeContext() } });
        expect(
            screen.getByPlaceholderText("Add comments..."),
        ).toBeInTheDocument();
    });

    it("calls updateSubTask when a status button is clicked", async () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        await fireEvent.click(screen.getByRole("button", { name: "Busy" }));
        expect(updateSubTask).toHaveBeenCalledWith(7, { task_state: "Busy" });
    });

    it("calls updateSubTaskComments when comments change", async () => {
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify({ "42": true }),
        );
        render(TaskPanel, { props: { taskContext: makeContext() } });
        const textarea = screen.getByPlaceholderText("Add comments...");
        await fireEvent.change(textarea, { target: { value: "updated" } });
        expect(updateSubTaskComments).toHaveBeenCalledWith(7, "updated");
    });
    it("shows a toast when status update fails", async () => {
        updateSubTask.mockRejectedValueOnce(new Error("network"));
        render(TaskPanel, { props: { taskContext: makeContext() } });
        await fireEvent.click(screen.getByRole("button", { name: "Busy" }));
        expect(toast.error).toHaveBeenCalledWith("Error: network");
    });

    it("shows a toast when comments update fails", async () => {
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify({ "42": true }),
        );
        updateSubTaskComments.mockRejectedValueOnce(new Error("save failed"));
        render(TaskPanel, { props: { taskContext: makeContext() } });
        const textarea = screen.getByPlaceholderText("Add comments...");
        await fireEvent.change(textarea, { target: { value: "updated" } });
        expect(toast.error).toHaveBeenCalledWith("Error: save failed");
    });
});
