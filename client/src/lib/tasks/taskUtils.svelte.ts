/**
 * Utility functions for task navigation
 */

import type { TaskContext } from "./TaskContext.svelte";

/**
 * Opens another set of the task with a full page load. Only the `layout` and `arrange` params carry over.
 *
 * @param index - The subtask index to navigate to
 */
export function navigateSubtaskIndex(index: number): void {
    const { pathname, search } = window.location;
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- read once, never reactive state
    const params = new URLSearchParams(search);
    // ASSUMPTION: v= and page= name the last set's images, so only the grader's layout and order carry over (plan decision 26).
    const query = ["layout", "arrange"]
        .flatMap((key) => {
            const value = params.get(key);
            return value === null
                ? []
                : [`${key}=${encodeURIComponent(value)}`];
        })
        .join("&");
    window.location.href =
        pathname.substring(0, pathname.lastIndexOf("/") + 1) +
        index +
        (query ? `?${query}` : "");
}

export class TaskNavigation {
    prevDisabled: boolean;
    nextDisabled: boolean;

    constructor(private taskContext: TaskContext) {
        this.prevDisabled = $derived(this.taskContext.subTaskIndex === 0);
        this.nextDisabled = $derived(
            this.taskContext.subTaskIndex >=
                this.taskContext.task.num_tasks - 1,
        );
    }

    prev(): void {
        if (this.prevDisabled) return;
        navigateSubtaskIndex(this.taskContext.subTaskIndex - 1);
    }

    next(): void {
        if (this.nextDisabled) return;
        navigateSubtaskIndex(this.taskContext.subTaskIndex + 1);
    }
}
