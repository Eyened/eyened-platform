<script lang="ts">
    import { page } from "$app/state";
    import { ButtonGroup } from "$lib/components/ui/button-group";
    import Button from "$lib/components/ui/button/button.svelte";
    import { updateSubTaskComments } from "$lib/data";
    import { updateSubTask } from "$lib/data/api";
    import ChevronLeft from "@lucide/svelte/icons/chevron-left";
    import ChevronRight from "@lucide/svelte/icons/chevron-right";
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

    const navigation = new TaskNavigation(taskContext);
    const subTask = $derived(taskContext.subTask);
    const task = $derived(taskContext.task);
    const subTaskIndex = $derived(taskContext.subTaskIndex);
    const panelConfig = $derived(
        parseTaskPanelConfig(task.task_definition.config),
    );
    const showExpandControl = $derived(
        panelConfig.sections.comments || panelConfig.sections.overview,
    );

    let expanded = $state(false);
    let isUpdatingState = $state(false);

    $effect(() => {
        expanded = getTaskPanelExpanded(task.id, panelConfig.expanded);
    });

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
    <aside
        class="task-panel"
        class:expanded
        aria-label="Task"
    >
        {#if showExpandControl}
            <div class="controls">
                <Button
                    variant="outline"
                    size="sm"
                    onclick={toggleExpanded}
                    aria-expanded={expanded}
                    aria-label={expanded
                        ? "Collapse task panel"
                        : "Expand task panel"}
                >
                    {expanded ? "Collapse" : "Expand"}
                </Button>
            </div>
        {/if}

        {#if panelConfig.sections.title}
            <div class="title">Set {subTaskIndex} of {task.num_tasks}</div>
        {/if}

        {#if panelConfig.sections.nav}
            <div class="controls">
                <ButtonGroup orientation="vertical">
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.prev()}
                        disabled={navigation.prevDisabled}
                        aria-label="Previous subtask"
                    >
                        <ChevronLeft />
                        Previous
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.next()}
                        disabled={navigation.nextDisabled}
                        aria-label="Next subtask"
                    >
                        Next
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
                        rows="6"
                        value={subTask.comments || ""}
                        onchange={async (e) => {
                            const target = e.target as HTMLTextAreaElement;
                            await updateComments(target.value);
                        }}
                        class="min-h-[60px] w-full rounded border p-2"
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
        flex: 0 0 10rem;
        z-index: 2;
        background-color: black;
        color: rgba(255, 255, 255, 0.9);
        border-left: 1px solid rgba(255, 255, 255, 0.4);
        padding: 0.5rem;
        gap: 0.5rem;
        overflow-y: auto;
        overflow-x: hidden;
    }
    aside.task-panel.expanded {
        flex-basis: 18rem;
    }
    .title {
        font-weight: bold;
        font-size: 0.85rem;
        text-align: center;
    }
    .controls {
        display: flex;
        flex-direction: column;
        align-items: stretch;
    }
    .busy {
        opacity: 0.6;
        pointer-events: none;
        cursor: wait;
    }
    .comments {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        font-size: 0.85rem;
    }
    textarea {
        background-color: white;
        color: black;
    }
</style>
