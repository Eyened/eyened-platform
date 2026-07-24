<script lang="ts">
    import { goto } from "$app/navigation";
    import { page as appPage } from "$app/state";
    import FixedSpinner from "$lib/components/FixedSpinner.svelte";
    import Main from "$lib/components/Main.svelte";
    import SubtasksTable from "$lib/tasks/SubtasksTable.svelte";
    import { getContext, onMount } from "svelte";
    import { ButtonGroup } from "$lib/components/ui/button-group";
    import Button from "$lib/components/ui/button/button.svelte";
    import {
        fetchSubTaskAssignees,
        fetchSubTasks,
        fetchTask,
    } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { subtasks, tasks } from "$lib/data/stores.svelte";
    import Label from "../../../lib/components/ui/label/label.svelte";
    import { subTaskStates } from "../../../types/openapi_constants";
    import type { SubTaskState } from "../../../types/openapi_types";

    let { data } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");

    let isLoading: boolean = $state(true);

    let task = $derived(tasks.get(data.taskid));
    let subtasksArray = $derived(Array.from(subtasks.values()));

    let subtasksCount: number = $state(0);
    let subtasksLimit: number = $state(20);
    let subtasksPage: number = $state(0);

    let subtasksStatus: SubTaskState | null = $state(null);
    /** null=all, "unassigned", or creator id number */
    let assigneeFilter: null | "unassigned" | number = $state(null);
    let assignees: { id: number; name: string }[] = $state([]);

    async function loadAssignees() {
        try {
            assignees = await fetchSubTaskAssignees(data.taskid);
        } catch (e) {
            console.error("Failed to load assignees", e);
            assignees = [];
        }
    }

    async function fetchCurrentPage() {
        const nextPage = Math.max(0, subtasksPage);
        subtasks.clear();
        const res = await fetchSubTasks({
            task_id: data.taskid,
            with_images: true,
            limit: subtasksLimit,
            page: nextPage,
            subtask_status: subtasksStatus ?? undefined,
            unassigned: assigneeFilter === "unassigned" ? true : undefined,
            creator_id:
                typeof assigneeFilter === "number" ? assigneeFilter : undefined,
        });

        subtasksCount = res.count;
        subtasksLimit = res.limit;
        subtasksPage = res.page;

        // If this page emptied after claim/unclaim, step back one page.
        if (
            (res.subtasks?.length ?? 0) === 0 &&
            subtasksPage > 0 &&
            subtasksCount > 0
        ) {
            subtasksPage = subtasksPage - 1;
            await fetchCurrentPage();
            return;
        }

        const url = new URL(window.location.href);
        url.searchParams.set("page", String(subtasksPage));
        url.searchParams.set("limit", String(subtasksLimit));
        if (subtasksStatus)
            url.searchParams.set("status", String(subtasksStatus));
        else url.searchParams.delete("status");
        if (assigneeFilter === "unassigned") {
            url.searchParams.set("unassigned", "1");
            url.searchParams.delete("creator_id");
        } else if (typeof assigneeFilter === "number") {
            url.searchParams.set("creator_id", String(assigneeFilter));
            url.searchParams.delete("unassigned");
        } else {
            url.searchParams.delete("unassigned");
            url.searchParams.delete("creator_id");
        }
        await goto(url.pathname + "?" + url.searchParams.toString(), {
            replaceState: true,
            noScroll: true,
            keepFocus: true,
        });
    }

    async function loadPage(p: number): Promise<void> {
        isLoading = true;
        try {
            await fetchTask(data.taskid);
            await loadAssignees();
            subtasksPage = Math.max(0, Number.isFinite(p) ? p : 0);
            await fetchCurrentPage();
        } finally {
            isLoading = false;
        }
    }

    /** Quiet refresh after claim/unclaim — keeps filters, updates rows + assignees. */
    async function refreshAfterAssignment() {
        await loadAssignees();
        await fetchCurrentPage();
    }

    onMount(async () => {
        try {
            const sp = appPage.url.searchParams;
            const qpLimit = Number(sp.get("limit"));
            const qpPage = Number(sp.get("page"));
            const qpStatus = sp.get("status");
            const qpUnassigned = sp.get("unassigned");
            const qpCreator = Number(sp.get("creator_id"));

            if (Number.isFinite(qpLimit) && qpLimit > 0)
                subtasksLimit = qpLimit;
            if (Number.isFinite(qpPage) && qpPage >= 0) subtasksPage = qpPage;
            if (
                qpStatus &&
                (subTaskStates as readonly string[]).includes(qpStatus)
            ) {
                subtasksStatus = qpStatus as SubTaskState;
            }
            if (qpUnassigned === "1" || qpUnassigned === "true") {
                assigneeFilter = "unassigned";
            } else if (Number.isFinite(qpCreator) && qpCreator > 0) {
                assigneeFilter = qpCreator;
            }

            await loadPage(subtasksPage);
        } catch (error) {
            console.error("Error loading task page:", error);
            isLoading = false;
        }
    });

    function selectStatus(s: SubTaskState | null) {
        subtasksStatus = s;
        loadPage(0);
    }

    function selectAssignee(value: null | "unassigned" | number) {
        assigneeFilter = value;
        loadPage(0);
    }

    function deselect() {
        const currentUrl = window.location.href;
        const lastSlashIndex = currentUrl.lastIndexOf("/");

        const suffix_string = `?${appPage.url.searchParams.toString()}`;
        const newUrl =
            currentUrl.substring(0, lastSlashIndex + 1) + suffix_string;

        goto(newUrl);
    }
</script>

{#if isLoading}
    <FixedSpinner />
{:else}
    <Main>
        {#snippet children()}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div id="main">
                <h3>
                    <span onclick={deselect} onkeypress={deselect}> ... </span>
                </h3>
                {#if !task}
                    Task not found
                {:else}
                    <h1>{task.name}</h1>
                    {#if task.task_state}
                        <h3>Status: {task.task_state}</h3>
                    {/if}
                    <div class="filter-bar mb-4">
                        <h2 class="filter-title">Filter</h2>
                        <div class="filters">
                            <div class="filter-group">
                                <Label>Status:</Label>
                                <ButtonGroup>
                                    <Button
                                        size="sm"
                                        variant={subtasksStatus === null
                                            ? "default"
                                            : "outline"}
                                        aria-pressed={subtasksStatus === null}
                                        onclick={() => selectStatus(null)}
                                    >
                                        All
                                    </Button>
                                    {#each subTaskStates as s}
                                        <Button
                                            size="sm"
                                            variant={subtasksStatus === s
                                                ? "default"
                                                : "outline"}
                                            aria-pressed={subtasksStatus === s}
                                            onclick={() => selectStatus(s)}
                                        >
                                            {s}
                                        </Button>
                                    {/each}
                                </ButtonGroup>
                            </div>

                            <div class="filter-group">
                                <Label>Assignee:</Label>
                                <div class="assignee-controls">
                                    <ButtonGroup>
                                        <Button
                                            size="sm"
                                            variant={assigneeFilter === null
                                                ? "default"
                                                : "outline"}
                                            aria-pressed={assigneeFilter ===
                                                null}
                                            onclick={() => selectAssignee(null)}
                                        >
                                            All
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant={assigneeFilter ===
                                            "unassigned"
                                                ? "default"
                                                : "outline"}
                                            aria-pressed={assigneeFilter ===
                                                "unassigned"}
                                            onclick={() =>
                                                selectAssignee("unassigned")}
                                        >
                                            Unassigned
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant={assigneeFilter ===
                                            globalContext.user.id
                                                ? "default"
                                                : "outline"}
                                            aria-pressed={assigneeFilter ===
                                                globalContext.user.id}
                                            onclick={() =>
                                                selectAssignee(
                                                    globalContext.user.id,
                                                )}
                                        >
                                            Mine
                                        </Button>
                                    </ButtonGroup>
                                    {#if assignees.length > 0}
                                        <label
                                            class="flex items-center gap-2 text-sm"
                                        >
                                            Pick:
                                            <select
                                                class="rounded border px-2 py-1 text-sm"
                                                value={typeof assigneeFilter ===
                                                "number"
                                                    ? String(assigneeFilter)
                                                    : ""}
                                                onchange={(e) => {
                                                    const v = (
                                                        e.currentTarget as HTMLSelectElement
                                                    ).value;
                                                    if (!v)
                                                        selectAssignee(null);
                                                    else
                                                        selectAssignee(
                                                            Number(v),
                                                        );
                                                }}
                                            >
                                                <option value="">—</option>
                                                {#each assignees as a}
                                                    <option value={a.id}
                                                        >{a.name}</option
                                                    >
                                                {/each}
                                            </select>
                                        </label>
                                    {/if}
                                </div>
                            </div>
                        </div>
                    </div>

                    <SubtasksTable
                        rows={subtasksArray}
                        taskId={data.taskid}
                        count={subtasksCount}
                        page={subtasksPage}
                        perPage={subtasksLimit}
                        onPageChange={loadPage}
                        onAssignmentChange={refreshAfterAssignment}
                    />
                {/if}
            </div>
        {/snippet}
    </Main>
{/if}

<style>
    span {
        cursor: pointer;
        font-size: large;
        font-weight: bold;
    }
    div#main {
        width: 100%;
        max-width: 1440px;
        margin: 0 auto;
        display: flex;
        padding: 1em 3em;
        flex-direction: column;
        overflow: auto;
    }
    .filter-bar {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        padding: 0.75rem 1rem;
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.03);
    }
    .filter-title {
        margin: 0;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: rgba(0, 0, 0, 0.55);
    }
    .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 1.25rem 2rem;
        align-items: flex-end;
    }
    .filter-group {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    .filter-group :global(button) {
        height: 1.75rem;
        padding-left: 0.55rem;
        padding-right: 0.55rem;
        font-size: 0.8rem;
    }
    .assignee-controls {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: center;
    }
</style>
