<script lang="ts">
    import { page } from "$app/state";
    import Button from "$lib/components/ui/button/button.svelte";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { TextArea } from "$lib/components/ui/text-area/index.js";
    import { updateSubTaskComments } from "$lib/data";
    import { updateSubTask } from "$lib/data/api";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import Maximize from "carbon-icons-svelte/lib/Maximize.svelte";
    import Minimize from "carbon-icons-svelte/lib/Minimize.svelte";
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
                    <IconButton
                        label={expanded
                            ? "Collapse task panel"
                            : "Expand task panel"}
                        class="toggle"
                        onclick={toggleExpanded}
                        aria-expanded={expanded}
                    >
                        {#if expanded}
                            <Minimize />
                        {:else}
                            <Maximize />
                        {/if}
                    </IconButton>
                {/if}
                {#if panelConfig.sections.title}
                    <div class="title">
                        Set {subTaskIndex}
                    </div>
                {/if}
            </div>
        {/if}

        {#if panelConfig.sections.nav}
            <div class="controls nav">
                <IconButton
                    label="Previous subtask"
                    onclick={() => navigation.prev()}
                    disabled={navigation.prevDisabled}
                >
                    <ChevronLeft />
                </IconButton>
                <IconButton
                    label="Next subtask"
                    onclick={() => navigation.next()}
                    disabled={navigation.nextDisabled}
                >
                    <ChevronRight />
                </IconButton>
            </div>
        {/if}

        {#if panelConfig.sections.status}
            <div class="controls">
                <div
                    class="status"
                    class:busy={isUpdatingState}
                    aria-busy={isUpdatingState}
                >
                    {#each subTaskStates as state (state)}
                        {@const isActive = subTask.task_state === state}
                        <Button
                            variant={isActive ? "default" : "ghost"}
                            size="sm"
                            disabled={isUpdatingState}
                            onclick={() => !isActive && setState(state)}
                            aria-pressed={isActive}
                        >
                            {state}
                        </Button>
                    {/each}
                </div>
            </div>
        {/if}

        {#if expanded}
            {#if panelConfig.sections.comments}
                <TextArea
                    labelText="Comments"
                    value={subTask.comments || ""}
                    onchange={async (e) => {
                        const target = e.target as HTMLTextAreaElement;
                        await updateComments(target.value);
                    }}
                    placeholder="Add comments..."
                />
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
        color: var(--color-text-primary);
        border-left: 1px solid var(--color-border-strong-01);
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
    .nav {
        flex-direction: row;
    }
    .status {
        display: flex;
        flex-direction: column;
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
</style>
