import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { ingestTasks, subtasks, tasks } from "$lib/data/stores.svelte";
import type { TaskGET } from "../../../types/openapi_types";

const { goto, pageState } = vi.hoisted(() => ({
    goto: vi.fn(),
    pageState: { url: new URL("http://localhost/tasks/9") },
}));

vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$app/paths", () => ({
    resolve: (path: string) => path,
}));
vi.mock("$app/state", () => ({
    page: pageState,
}));
vi.mock(
    "$lib/components/Main.svelte",
    async () => import("../../../../vitest-passthrough.svelte"),
);
vi.mock("$lib/data/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("$lib/data/api")>();
    return {
        ...actual,
        fetchTask: vi.fn(),
        fetchSubTasks: vi.fn(),
        fetchSubTaskAssignees: vi.fn(),
    };
});

const { fetchTask, fetchSubTasks, fetchSubTaskAssignees } = await import(
    "$lib/data/api"
);
const { default: TaskPage } = await import("./+page.svelte");

function makeTask(overrides: Partial<TaskGET> = {}): TaskGET {
    return {
        id: 9,
        name: "Grading task",
        description: null,
        contact_id: null,
        task_definition_id: 1,
        date_inserted: "2026-01-01T00:00:00",
        num_tasks: 1,
        num_tasks_ready: 1,
        creator: null,
        task_state: "active",
        task_definition: {
            id: 1,
            name: "Definition",
            config: {},
            date_inserted: "2026-01-01T00:00:00",
        },
        projects: null,
        ...overrides,
    };
}

const context = new Map([
    [
        "globalContext",
        {
            user: { id: 5 },
            userManager: { loggedIn: true, user: { id: 5 } },
        },
    ],
]);

describe("task subtasks page", () => {
    beforeEach(() => {
        tasks.clear();
        subtasks.clear();
        goto.mockReset();
        pageState.url = new URL("http://localhost/tasks/9");
        vi.mocked(fetchTask).mockImplementation(async () => {
            ingestTasks([makeTask()]);
            return makeTask();
        });
        vi.mocked(fetchSubTasks).mockResolvedValue({
            subtasks: [{ id: 1, index: 0, images: [] }],
            count: 1,
            page: 0,
            limit: 20,
        });
        vi.mocked(fetchSubTaskAssignees).mockResolvedValue([
            { id: 4, name: "alice" },
        ]);
    });

    it("loads filters from the query string and lists subtasks", async () => {
        pageState.url = new URL(
            "http://localhost/tasks/9?page=0&limit=10&status=NotStarted&unassigned=1",
        );
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);

        await waitFor(() => {
            expect(screen.getByText("Grading task")).toBeInTheDocument();
        });
        expect(fetchSubTasks).toHaveBeenCalledWith(
            expect.objectContaining({
                task_id: 9,
                limit: 10,
                page: 0,
                subtask_status: "NotStarted",
                unassigned: true,
            }),
        );
        expect(screen.getByText("alice")).toBeInTheDocument();
        expect(screen.getByText("Status: active")).toBeInTheDocument();
    });

    it("filters by creator from the query string", async () => {
        pageState.url = new URL("http://localhost/tasks/9?creator_id=4");
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);

        await waitFor(() => {
            expect(fetchSubTasks).toHaveBeenCalledWith(
                expect.objectContaining({ creator_id: 4 }),
            );
        });
    });

    it("steps back a page when the current page is empty", async () => {
        pageState.url = new URL("http://localhost/tasks/9?page=1");
        vi.mocked(fetchSubTasks)
            .mockResolvedValueOnce({
                subtasks: [],
                count: 5,
                page: 1,
                limit: 20,
            })
            .mockResolvedValueOnce({
                subtasks: [{ id: 1, index: 0, images: [] }],
                count: 5,
                page: 0,
                limit: 20,
            });

        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);

        await waitFor(() => {
            expect(fetchSubTasks).toHaveBeenCalledTimes(2);
        });
        expect(fetchSubTasks).toHaveBeenLastCalledWith(
            expect.objectContaining({ page: 0 }),
        );
    });

    it("changes status and assignee filters", async () => {
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);
        await waitFor(() => {
            expect(screen.getByText("Grading task")).toBeInTheDocument();
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "NotStarted" }),
        );
        await waitFor(() => {
            expect(fetchSubTasks).toHaveBeenCalledWith(
                expect.objectContaining({ subtask_status: "NotStarted" }),
            );
            expect(
                screen.getByRole("button", { name: "Unassigned" }),
            ).toBeInTheDocument();
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Unassigned" }),
        );
        await waitFor(() => {
            expect(fetchSubTasks).toHaveBeenCalledWith(
                expect.objectContaining({ unassigned: true }),
            );
            expect(screen.getByDisplayValue("—")).toBeInTheDocument();
        });

        const pick = screen.getByDisplayValue("—") as HTMLSelectElement;
        await fireEvent.change(pick, { target: { value: "4" } });
        await waitFor(() => {
            expect(fetchSubTasks).toHaveBeenCalledWith(
                expect.objectContaining({ creator_id: 4 }),
            );
        });
    });

    it("shows task not found when the store has no task", async () => {
        vi.mocked(fetchTask).mockResolvedValue(makeTask());
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);
        await waitFor(() => {
            expect(screen.getByText("Task not found")).toBeInTheDocument();
        });
    });

    it("swallows assignee load errors", async () => {
        vi.mocked(fetchSubTaskAssignees).mockRejectedValue(new Error("nope"));
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);
        await waitFor(() => {
            expect(screen.getByText("Grading task")).toBeInTheDocument();
        });
        expect(screen.queryByText("alice")).not.toBeInTheDocument();
    });
});
