import { describe, it, expect, vi, beforeEach } from "vitest";
import { subtasks } from "./stores.svelte";

vi.mock("../api/client", async (importOriginal) => {
    const actual = await importOriginal<typeof import("../api/client")>();
    return {
        ...actual,
        api: {
            GET: vi.fn(),
            POST: vi.fn(),
            PATCH: vi.fn(),
            DELETE: vi.fn(),
        },
        withAuthRetry: async (fn: () => Promise<unknown>) => fn(),
        isUnauthorizedStatus: (status: number) =>
            status === 401 || status === 403,
        fetchApi: vi.fn(),
    };
});

const { api, ApiError } = await import("../api/client");
const { fetchSubTasks, fetchSubTaskAssignees, updateSubTask } = await import(
    "./api"
);

function ok<T>(data: T) {
    return { data, error: undefined, response: { status: 200 } as Response };
}

describe("subtask API helpers", () => {
    beforeEach(() => {
        subtasks.clear();
        vi.mocked(api.GET).mockReset();
        vi.mocked(api.PATCH).mockReset();
    });

    it("lists subtasks with filters and ingests them", async () => {
        const row = { id: 1, index: 0, images: [] };
        vi.mocked(api.GET).mockResolvedValue(
            ok({ subtasks: [row], count: 1, page: 0, limit: 20 }),
        );

        const data = await fetchSubTasks({
            task_id: 9,
            subtask_status: "todo",
            unassigned: true,
            creator_id: 4,
            page: 2,
            limit: 10,
        });

        expect(api.GET).toHaveBeenCalledWith(
            "/task/{task_id}/subtasks",
            expect.objectContaining({
                params: {
                    path: { task_id: 9 },
                    query: expect.objectContaining({
                        subtask_status: "todo",
                        unassigned: true,
                        creator_id: 4,
                        page: 2,
                        limit: 10,
                    }),
                },
            }),
        );
        expect(data.count).toBe(1);
        expect(subtasks.get(1)).toMatchObject({ id: 1 });
    });

    it("fetches subtask assignees", async () => {
        vi.mocked(api.GET).mockResolvedValue(ok([{ id: 4, name: "alice" }]));
        const assignees = await fetchSubTaskAssignees(9);
        expect(api.GET).toHaveBeenCalledWith(
            "/task/{task_id}/subtask-assignees",
            { params: { path: { task_id: 9 } } },
        );
        expect(assignees).toEqual([{ id: 4, name: "alice" }]);
    });

    it("patches a claim and ingests the result", async () => {
        vi.mocked(api.PATCH).mockResolvedValue(
            ok({ id: 1, index: 0, images: [], creator_id: 4 }),
        );
        const updated = await updateSubTask(1, { claim: true });
        expect(api.PATCH).toHaveBeenCalledWith(
            "/subtasks/{subtaskid}",
            expect.objectContaining({
                body: { claim: true },
            }),
        );
        expect(updated.creator_id).toBe(4);
        expect(subtasks.get(1)?.creator_id).toBe(4);
    });

    it("throws ApiError with conflict detail when claim returns 409", async () => {
        vi.mocked(api.PATCH).mockResolvedValue({
            data: undefined,
            error: {
                detail: {
                    code: "subtask_already_claimed",
                    message: "SubTask is already assigned",
                    creator_id: 4,
                },
            },
            response: { status: 409 } as Response,
        });

        try {
            await updateSubTask(1, { claim: true });
            throw new Error("expected updateSubTask to throw");
        } catch (error) {
            expect(error).toBeInstanceOf(ApiError);
            const apiError = error as InstanceType<typeof ApiError>;
            expect(apiError.status).toBe(409);
            expect(apiError.message).toBe("SubTask is already assigned");
            expect(apiError.code).toBe("subtask_already_claimed");
        }
    });
});
