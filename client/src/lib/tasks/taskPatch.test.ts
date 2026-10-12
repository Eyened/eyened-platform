import { describe, expect, it } from "vitest";
import type { TaskGET } from "../../types/openapi_types";
import { taskPatch } from "./taskPatch";

const task = {
    name: "Alpha",
    description: null,
    task_state: "Busy",
} as TaskGET;

describe("taskPatch", () => {
    it("holds only the changed fields, so a status-only edit sends only the status", () => {
        expect(
            taskPatch(task, {
                name: "Alpha",
                description: "",
                task_state: "Finished",
            }),
        ).toEqual({ task_state: "Finished" });
    });

    it("is null when nothing changed", () => {
        expect(
            taskPatch(task, {
                name: "Alpha",
                description: "",
                task_state: "Busy",
            }),
        ).toBeNull();
    });
});
