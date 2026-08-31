<script lang="ts">
    import { page } from "$app/state";
    import { ButtonGroup } from "$lib/components/ui/button-group";
    import Button from "$lib/components/ui/button/button.svelte";
    import { updateSubTaskComments } from "$lib/data";
    import { updateSubTask } from "$lib/data/api";
    import ChevronLeft from "@lucide/svelte/icons/chevron-left";
    import ChevronRight from "@lucide/svelte/icons/chevron-right";
    import Expand from "@lucide/svelte/icons/expand";
    import Shrink from "@lucide/svelte/icons/shrink";
    import { toast } from "svelte-sonner";
    import { subTaskStates } from "../../types/openapi_constants";
    import type { SubTaskState } from "../../types/openapi_types";
    import type { TaskContext } from "./TaskContext.svelte";
    import { parseTaskPanelConfig } from "./taskPanelConfig";
    import {
        getTaskPanelExpanded,
        setTaskPanelExpanded,
    } from "./taskPanelExpandedPrefs";
    import { TaskNavigation } from "./taskUtils.svelte";

    interface Props {
        taskContext: TaskContext;
    }

    let { taskContext }: Props = $props();

    const navigation = $derived.by(() => new TaskNavigation(taskContext));
    const subTask = $derived(taskContext.subTask);
    const task = $derived(taskContext.task);
    const subTaskIndex = $derived(taskContext.subTaskIndex);
    const panelConfig = $derived(
        parseTaskPanelConfig(task.task_definition.config),
    );
    const showExpandControl = $derived(
        panelConfig.sections.comments || panelConfig.sections.overview,
    );

    let isUpdatingState = $state(false);

    let expanded = $derived(
        getTaskPanelExpanded(task.id, panelConfig.expanded),
    );

    function toggleExpanded() {
        expanded = !expanded;
        setTaskPanelExpanded(task.id, expanded);
    }

    async function setState(state: SubTaskState) {
        isUpdatingState = true;
        try {
            await updateSubTask(subTask.id, { task_state: state });
        } catch (e) {
            toast.error(String(e));
        } finally {
            isUpdatingState = false;
        }
    }

    async function handleViewTask() {
        const suffix_string = `?${page.url.searchParams.toString()}`;
        const url = new URL(
            `${window.location.origin}/tasks/${task.id}${suffix_string}`,
        );
        window.location.href = url.href;
    }

    async function updateComments(comments: string) {
        try {
            await updateSubTaskComments(subTask.id, comments);
        } catch (e) {
            toast.error(String(e));
        }
    }
</script>

{#if panelConfig.enabled}
    <aside class="task-panel" class:expanded aria-label="Task">
        {#if showExpandControl || panelConfig.sections.title}
            <div class="header">
                {#if showExpandControl}
                    <Button
                        variant="outline"
                        size="sm"
                        class="toggle"
                        onclick={toggleExpanded}
                        aria-expanded={expanded}
                        aria-label={expanded
                            ? "Collapse task panel"
                            : "Expand task panel"}
                    >
                        {#if expanded}
                            <Shrink />
                        {:else}
                            <Expand />
                        {/if}
                    </Button>
                {/if}
                {#if panelConfig.sections.title}
                    <div class="title">
                        Set {subTaskIndex} of {task.num_tasks}
                    </div>
                {/if}
            </div>
        {/if}

        {#if panelConfig.sections.nav}
            <div class="controls nav">
                <ButtonGroup orientation="horizontal">
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.prev()}
                        disabled={navigation.prevDisabled}
                        aria-label="Previous subtask"
                    >
                        <ChevronLeft />
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.next()}
                        disabled={navigation.nextDisabled}
                        aria-label="Next subtask"
                    >
                        <ChevronRight />
                    </Button>
                </ButtonGroup>
            </div>
        {/if}

        {#if panelConfig.sections.status}
            <div class="controls">
                <div class:busy={isUpdatingState} aria-busy={isUpdatingState}>
                    <ButtonGroup orientation="vertical">
                        {#each subTaskStates as state (state)}
                            {@const isActive = subTask.task_state === state}
                            <Button
                                variant={isActive ? "default" : "outline"}
                                size="sm"
                                disabled={isUpdatingState}
                                onclick={() => !isActive && setState(state)}
                                aria-pressed={isActive}
                                class={isActive ? "font-semibold" : ""}
                            >
                                {state}
                            </Button>
                        {/each}
                    </ButtonGroup>
                </div>
            </div>
        {/if}

        {#if expanded}
            {#if panelConfig.sections.comments}
                <div class="comments">
                    Comments:
                    <textarea
                        rows="4"
                        value={subTask.comments || ""}
                        onchange={async (e) => {
                            const target = e.target as HTMLTextAreaElement;
                            await updateComments(target.value);
                        }}
                        class="min-h-[48px] w-full rounded border p-1 text-xs"
                        placeholder="Add comments..."
                    ></textarea>
                </div>
            {/if}

            {#if panelConfig.sections.overview}
                <div class="controls">
                    <Button variant="outline" onclick={handleViewTask}
                        >Task overview</Button
                    >
                </div>
            {/if}
        {/if}
    </aside>
{/if}

<style>
    aside.task-panel {
        display: flex;
        flex-direction: column;
        flex: 0 0 9rem;
        z-index: 2;
        background-color: black;
        color: rgba(255, 255, 255, 0.9);
        border-left: 1px solid rgba(255, 255, 255, 0.4);
        padding: 0.25rem;
        gap: 0.2rem;
        overflow-y: auto;
        overflow-x: hidden;
        font-size: 0.75rem;
        line-height: 1.2;
    }
    aside.task-panel.expanded {
        flex-basis: 16rem;
    }
    .header {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.15rem;
    }
    aside.task-panel :global(button.toggle) {
        width: 1.35rem;
        flex: 0 0 1.35rem;
        padding-left: 0;
        padding-right: 0;
    }
    .title {
        flex: 1;
        font-weight: bold;
        font-size: 0.75rem;
        line-height: 1.2;
        text-align: center;
        padding: 0.1rem 0;
        min-width: 0;
    }
    .controls {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 0;
    }
    aside.task-panel :global([data-slot="button-group"]) {
        width: 100%;
    }
    .nav :global([data-slot="button-group"]) {
        display: flex;
        flex-direction: row;
    }
    .nav :global(button) {
        flex: 1;
        min-width: 0;
    }
    aside.task-panel :global(button) {
        height: 1.35rem;
        min-height: 1.35rem;
        padding-top: 0;
        padding-bottom: 0;
        padding-left: 0.35rem;
        padding-right: 0.35rem;
        font-size: 0.7rem;
        line-height: 1;
        width: 100%;
        justify-content: center;
        gap: 0.15rem;
    }
    aside.task-panel :global(button svg) {
        width: 0.8rem;
        height: 0.8rem;
    }
    .busy {
        opacity: 0.6;
        pointer-events: none;
        cursor: wait;
    }
    .comments {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        font-size: 0.75rem;
    }
    textarea {
        background-color: white;
        color: black;
        line-height: 1.2;
    }
</style>
