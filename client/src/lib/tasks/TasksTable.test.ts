import { fireEvent, render, screen } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ingestTasks, tasks } from "$lib/data/stores.svelte";
import type { TaskGET } from "../../types/openapi_types";

const { pageState } = vi.hoisted(() => ({
    pageState: { url: new URL("http://localhost/tasks") },
}));

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));
vi.mock("$app/paths", () => ({
    resolve: (path: string, params?: Record<string, string>) =>
        params ? path.replace("[taskid]", params.taskid) : path,
}));
vi.mock("$app/state", () => ({ page: pageState }));

const { default: TasksTable } = await import("./TasksTable.svelte");

function task(
    id: number,
    name: string,
    overrides: Partial<TaskGET> = {},
): TaskGET {
    return {
        id,
        name,
        description: null,
        contact_id: null,
        task_definition_id: 1,
        date_inserted: "2026-01-01T00:00:00",
        num_tasks: 0,
        num_tasks_ready: 0,
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

function renderTable(rows: TaskGET[]) {
    ingestTasks(rows);
    render(TasksTable, { props: { rows, headingId: "tasks-heading" } });
}

const taskNames = () =>
    screen.queryAllByRole("link").map((a) => a.textContent?.trim());

describe("TasksTable", () => {
    beforeEach(() => {
        tasks.clear();
        pageState.url = new URL("http://localhost/tasks");
    });

    it("shows renames and deletes made in the tasks store", () => {
        renderTable([task(1, "Alpha"), task(2, "Beta"), task(3, "Gamma")]);

        ingestTasks([task(1, "Alpha renamed")]);
        tasks.delete(2);
        flushSync();

        expect(taskNames()).toEqual(["Alpha renamed", "Gamma"]);
    });

    it("searches name, description and creator, ignoring case", async () => {
        renderTable([
            task(1, "Alpha"),
            task(2, "Beta", { description: "Drusen grading" }),
            task(3, "Gamma", { creator: { id: 7, name: "Ada" } }),
        ]);
        const search = screen.getByRole("searchbox", { name: "Search tasks" });

        await fireEvent.input(search, { target: { value: "DRUSEN" } });
        expect(taskNames()).toEqual(["Beta"]);

        await fireEvent.input(search, { target: { value: "ada" } });
        expect(taskNames()).toEqual(["Gamma"]);

        await fireEvent.input(search, { target: { value: "zzz" } });
        expect(screen.getByText("No tasks match “zzz”")).toBeInTheDocument();
    });

    it("hides archived tasks until Show archived is checked", async () => {
        renderTable([
            task(1, "Alpha"),
            task(2, "Old", { task_state: "Archived" }),
        ]);
        expect(taskNames()).toEqual(["Alpha"]);

        await fireEvent.click(
            screen.getByRole("checkbox", { name: "Show archived" }),
        );

        expect(taskNames()).toEqual(["Alpha", "Old"]);
    });
});
