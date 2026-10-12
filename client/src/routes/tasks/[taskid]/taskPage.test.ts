import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { ApiError } from "$lib/api/client";
import {
    ingestSubTasks,
    ingestTasks,
    subtasks,
    tasks,
} from "$lib/data/stores.svelte";
import type {
    SubTaskWithImagesGET,
    TaskGET,
} from "../../../types/openapi_types";

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
        updateSubTask: vi.fn(),
    };
});

const { fetchTask, fetchSubTasks, fetchSubTaskAssignees, updateSubTask } =
    await import("$lib/data/api");
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
        task_state: "Busy",
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

type SubtaskPage = {
    subtasks: SubTaskWithImagesGET[];
    count: number;
    page: number;
    limit: number;
};

// `length` subtasks from set `first` on, as GET /task/{id}/subtasks returns them.
function subtaskPage(
    first: number,
    length: number,
    count: number,
    overrides: Partial<SubTaskWithImagesGET> = {},
): SubtaskPage {
    return {
        subtasks: Array.from(
            { length },
            (_, i) =>
                ({
                    id: first + i + 1,
                    index: first + i,
                    task_id: 9,
                    task_state: "NotStarted",
                    comments: "",
                    images: [],
                    creator: null,
                    creator_id: null,
                    ...overrides,
                }) as SubTaskWithImagesGET,
        ),
        count,
        page: 0,
        limit: 20,
    };
}

// The real fetchSubTasks merges every response into the global store; so does this.
function respond(page: SubtaskPage) {
    ingestSubTasks(page.subtasks);
    return page;
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

function renderPage(url = "http://localhost/tasks/9") {
    pageState.url = new URL(url);
    render(TaskPage, {
        props: { data: { taskid: 9 } },
        context,
    } as never);
    return screen.findByRole("heading", { name: "Grading task" });
}

const setNumbers = () =>
    screen
        .queryAllByRole("link", { name: /^Set \d+, opens in a new tab$/ })
        .map((a) => a.textContent?.trim());

describe("task subtasks page", () => {
    beforeEach(() => {
        tasks.clear();
        subtasks.clear();
        goto.mockReset();
        vi.mocked(updateSubTask).mockReset();
        vi.mocked(fetchSubTasks).mockReset();
        vi.mocked(fetchTask).mockReset();
        vi.mocked(fetchTask).mockImplementation(async () => {
            ingestTasks([makeTask()]);
            return makeTask();
        });
        vi.mocked(fetchSubTasks).mockImplementation(async () =>
            respond(subtaskPage(0, 1, 1)),
        );
        vi.mocked(fetchSubTaskAssignees).mockResolvedValue([
            { id: 4, name: "alice" },
        ]);
    });

    it("loads filters from the query string and lists subtasks", async () => {
        await renderPage(
            "http://localhost/tasks/9?page=0&limit=10&status=NotStarted&unassigned=1",
        );
        expect(fetchSubTasks).toHaveBeenCalledWith(
            expect.objectContaining({
                task_id: 9,
                limit: 10,
                page: 0,
                subtask_status: "NotStarted",
                unassigned: true,
            }),
        );
        expect(setNumbers()).toEqual(["0"]);
    });

    it("filters by creator from the query string", async () => {
        await renderPage("http://localhost/tasks/9?creator_id=4");
        expect(fetchSubTasks).toHaveBeenCalledWith(
            expect.objectContaining({ creator_id: 4 }),
        );
    });

    it("changes a filter without reloading the task or remounting the page", async () => {
        const heading = await renderPage();

        await fireEvent.keyDown(
            screen.getByRole("button", { name: /^Status/ }),
            {
                key: "Enter",
            },
        );
        await fireEvent.pointerUp(
            await screen.findByRole("option", { name: "Not started" }),
        );

        await waitFor(() =>
            expect(fetchSubTasks).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    subtask_status: "NotStarted",
                    page: 0,
                }),
            ),
        );
        expect(screen.getByRole("heading", { name: "Grading task" })).toBe(
            heading,
        );
        expect(fetchTask).toHaveBeenCalledTimes(1);
    });

    it("shows a load error with the server's message", async () => {
        vi.mocked(fetchTask).mockRejectedValue(
            new ApiError(403, "Not allowed to view this task"),
        );
        pageState.url = new URL("http://localhost/tasks/9");
        render(TaskPage, {
            props: { data: { taskid: 9 } },
            context,
        } as never);

        expect(
            await screen.findByText("Task could not be loaded"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Not allowed to view this task"),
        ).toBeInTheDocument();
    });

    it("clamps a page past the end with one refetch", async () => {
        vi.mocked(fetchSubTasks).mockImplementation(async () =>
            respond(subtaskPage(20, 5, 25)),
        );
        await renderPage("http://localhost/tasks/9?page=5&limit=20");

        expect(fetchSubTasks).toHaveBeenCalledTimes(2);
        expect(fetchSubTasks).toHaveBeenLastCalledWith(
            expect.objectContaining({ page: 1 }),
        );
    });

    it("lists only the new page's rows after a page change", async () => {
        vi.mocked(fetchSubTasks)
            .mockImplementationOnce(async () => respond(subtaskPage(0, 20, 40)))
            .mockImplementationOnce(async () =>
                respond(subtaskPage(20, 20, 40)),
            );
        await renderPage();

        await fireEvent.click(
            screen.getByRole("button", { name: "Next page" }),
        );

        await waitFor(() =>
            expect(setNumbers()).toEqual(
                Array.from({ length: 20 }, (_, i) => String(20 + i)),
            ),
        );
    });

    it("ignores a slower response to an earlier page change", async () => {
        let finishFirst = () => {};
        vi.mocked(fetchSubTasks)
            .mockImplementationOnce(async () => respond(subtaskPage(0, 20, 60)))
            .mockImplementationOnce(
                () =>
                    new Promise((done) => {
                        finishFirst = () =>
                            done(respond(subtaskPage(20, 20, 60)));
                    }),
            )
            .mockImplementationOnce(async () =>
                respond(subtaskPage(40, 20, 60)),
            );
        await renderPage();

        await fireEvent.click(
            screen.getByRole("button", { name: "Next page" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Next page" }),
        );
        await waitFor(() => expect(setNumbers()[0]).toBe("40"));

        finishFirst();
        await new Promise((r) => setTimeout(r, 0));
        expect(setNumbers()[0]).toBe("40");
    });

    it("claims every unassigned set on the page", async () => {
        vi.mocked(fetchSubTasks).mockImplementation(async () =>
            respond({
                ...subtaskPage(0, 1, 2),
                subtasks: [
                    ...subtaskPage(0, 1, 2).subtasks,
                    ...subtaskPage(1, 1, 2, {
                        creator: { id: 5, name: "me" } as never,
                        creator_id: 5,
                    }).subtasks,
                ],
            }),
        );
        vi.mocked(updateSubTask).mockResolvedValue({});
        await renderPage();

        await fireEvent.click(
            screen.getByRole("button", { name: "Claim unassigned on page" }),
        );

        await waitFor(() => expect(fetchSubTasks).toHaveBeenCalledTimes(2));
        expect(updateSubTask).toHaveBeenCalledTimes(1);
        expect(updateSubTask).toHaveBeenCalledWith(1, { claim: true });
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("skips sets already claimed and reports the rest", async () => {
        vi.mocked(fetchSubTasks).mockImplementation(async () =>
            respond(subtaskPage(0, 2, 2)),
        );
        vi.mocked(updateSubTask)
            .mockRejectedValueOnce(
                new ApiError(409, "SubTask is already assigned", {
                    code: "subtask_already_claimed",
                }),
            )
            .mockRejectedValueOnce(new Error("fail"));
        await renderPage();

        await fireEvent.click(
            screen.getByRole("button", { name: "Claim unassigned on page" }),
        );

        expect(
            await screen.findByText("Claimed 0 of 2 sets"),
        ).toBeInTheDocument();
        expect(screen.getByText("fail")).toBeInTheDocument();
    });

    it("swallows assignee load errors", async () => {
        vi.mocked(fetchSubTaskAssignees).mockRejectedValue(new Error("nope"));
        await renderPage();
        expect(setNumbers()).toEqual(["0"]);
    });
});
