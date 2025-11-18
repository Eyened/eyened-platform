/**
 * Utility functions for task navigation
 */

import type { TaskContext } from "./TaskContext.svelte";

/**
 * Navigates to a specific subtask index, preserving search params but removing
 * "annotation" and "instances" parameters.
 * 
 * @param index - The subtask index to navigate to
 */
export function navigateSubtaskIndex(index: number): void {
    const currentUrl = window.location.href;
    const lastSlashIndex = currentUrl.lastIndexOf("/");
    const newUrl =
        currentUrl.substring(0, lastSlashIndex + 1) + index;
    window.location.href = newUrl;
}


export class TaskNavigation {
    prevDisabled: boolean;
    nextDisabled: boolean;

    constructor(private taskContext: TaskContext) {
        this.prevDisabled = $derived(this.taskContext.subTaskIndex === 0);
        this.nextDisabled = $derived(this.taskContext.subTaskIndex >= this.taskContext.task.num_tasks - 1);
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

