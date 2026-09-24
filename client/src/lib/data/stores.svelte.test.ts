import { describe, it, expect, beforeEach } from "vitest";
import { tasks, ingestTasks } from "./stores.svelte";
import type { TaskGET } from "../../types/openapi_types";

function makeTask(overrides: Partial<TaskGET> = {}): TaskGET {
    return {
        id: 1,
        name: "Task 1",
        description: null,
        contact_id: null,
        task_definition_id: 1,
        date_inserted: "2026-01-01T00:00:00",
        num_tasks: 1,
        num_tasks_ready: 1,
        creator: null,
        task_state: null,
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

describe("ingestTasks", () => {
    beforeEach(() => {
        tasks.clear();
    });

    it("preserves an existing task's projects when a later payload omits them", () => {
        // Detail fetch: GET /task/{id} always resolves projects.
        ingestTasks([makeTask({ id: 1, projects: [{ id: 1, name: "P1" }] })]);

        // List refresh: GET /task omits projects unless ?include_projects=true,
        // so the payload carries projects: null ("not requested", not "spans
        // nothing"). It must not clobber the value the detail fetch stored.
        ingestTasks([makeTask({ id: 1, projects: null })]);

        expect(tasks.get(1)?.projects).toEqual([{ id: 1, name: "P1" }]);
    });

    it("overwrites projects when a later payload provides a non-null value", () => {
        ingestTasks([makeTask({ id: 1, projects: [{ id: 1, name: "P1" }] })]);

        // A genuine ?include_projects=true refresh with changed spans must win.
        ingestTasks([makeTask({ id: 1, projects: [{ id: 2, name: "P2" }] })]);

        expect(tasks.get(1)?.projects).toEqual([{ id: 2, name: "P2" }]);
    });

    it("stores a new task as-is, including a null projects", () => {
        ingestTasks([makeTask({ id: 1, projects: null })]);

        expect(tasks.get(1)?.projects).toBeNull();
    });
});
