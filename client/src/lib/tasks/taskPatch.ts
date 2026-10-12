import type { TaskGET, TaskPATCH, TaskState } from "../../types/openapi_types";

export type TaskForm = {
    name: string;
    description: string;
    task_state: TaskState | null;
};

/**
 * The fields of `form` that differ from `task`, or null when none do. The server
 * requires project_admin whenever name or description is sent, so sending only
 * what changed lets a grader change the status.
 */
export function taskPatch(task: TaskGET, form: TaskForm): TaskPATCH | null {
    const patch: TaskPATCH = {};
    if (form.name !== task.name) patch.name = form.name;
    if (form.description !== (task.description ?? ""))
        patch.description = form.description;
    if (form.task_state !== (task.task_state ?? null))
        patch.task_state = form.task_state;
    return Object.keys(patch).length > 0 ? patch : null;
}
