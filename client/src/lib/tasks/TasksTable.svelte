<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Label } from "$lib/components/ui/label/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { ProgressBar } from "$lib/components/ui/progress-bar/index.js";
    import {
        SelectInput,
        SelectItem,
    } from "$lib/components/ui/select-input/index.js";
    import { StatusIndicator } from "$lib/components/ui/status-indicator/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { TextArea } from "$lib/components/ui/text-area/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import { deleteTask, updateTask } from "$lib/data/helpers";
    import { tasks } from "$lib/data/stores.svelte";
    import Edit from "carbon-icons-svelte/lib/Edit.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import type { TaskGET, TaskState } from "../../types/openapi_types";
    import { taskPatch } from "./taskPatch";
    import { TASK_STATES, TASK_STATUS } from "./taskStatus";

    // rows: the list GET /task returned, in its order; the store holds each task's latest version.
    let { rows, headingId }: { rows: TaskGET[]; headingId: string } = $props();

    const archivedId = $props.id();

    let search = $state(page.url.searchParams.get("search") ?? "");
    let showArchived = $state(page.url.searchParams.get("archived") === "1");

    // Deleted tasks drop out; edited tasks show their new values.
    const current = $derived(
        rows.flatMap((r) => {
            const t = tasks.get(r.id);
            return t ? [t] : [];
        }),
    );
    const listed = $derived(
        showArchived
            ? current
            : current.filter((t) => t.task_state !== "Archived"),
    );
    const query = $derived(search.trim().toLowerCase());
    const visible = $derived(
        query
            ? listed.filter((t) =>
                  [t.name, t.description, t.creator?.name].some((s) =>
                      s?.toLowerCase().includes(query),
                  ),
              )
            : listed,
    );

    // Same route, only the query string changes (as /tasks/[taskid] does), so opening a
    // task and going back keeps the search.
    function syncUrl() {
        // Built without mutation: svelte/prefer-svelte-reactivity flags a mutated URLSearchParams.
        const entries: [string, string][] = [];
        if (search.trim()) entries.push(["search", search.trim()]);
        if (showArchived) entries.push(["archived", "1"]);
        const qs = new URLSearchParams(entries).toString();
        goto(qs ? resolve(`/tasks?${qs}`) : resolve("/tasks"), {
            replaceState: true,
            keepFocus: true,
            noScroll: true,
        });
    }

    let editing = $state<TaskGET | null>(null);
    let editOpen = $state(false);
    let form = $state({ name: "", description: "", task_state: "" });
    let nameMissing = $state(false);

    function openEdit(t: TaskGET) {
        editing = t;
        form = {
            name: t.name,
            description: t.description ?? "",
            task_state: t.task_state ?? "",
        };
        nameMissing = false;
        editOpen = true;
    }

    function saveEdit() {
        if (!editing) return false;
        const name = form.name.trim();
        if (!name) {
            nameMissing = true;
            return false;
        }
        const patch = taskPatch(editing, {
            name,
            description: form.description,
            task_state: (form.task_state || null) as TaskState | null,
        });
        if (!patch) {
            editOpen = false;
            return false;
        }
        return updateTask(editing.id, patch);
    }

    let deleting = $state<TaskGET | null>(null);
    let deleteOpen = $state(false);

    function openDelete(t: TaskGET) {
        deleting = t;
        deleteOpen = true;
    }

    function confirmDelete() {
        return deleting ? deleteTask(deleting.id) : false;
    }

    function deleteBody(t: TaskGET) {
        const n = t.num_tasks;
        if (n === 0) return "Deletes the task. This can't be undone.";
        return `Deletes the task and its ${n} ${n === 1 ? "subtask" : "subtasks"}. Gradings and segmentations are kept but lose their link to the task. This can't be undone.`;
    }

    // The deleted row's button is gone, so focus goes to the page heading.
    function focusHeadingIfDeleted(event: Event) {
        if (deleting && !tasks.has(deleting.id)) {
            event.preventDefault();
            document.getElementById(headingId)?.focus();
        }
    }
</script>

{#if current.length === 0}
    <Empty.Root>
        <Empty.Header>
            <Empty.Title>No tasks yet</Empty.Title>
            <Empty.Description>
                Tasks appear here when one is created in a project you belong
                to.
            </Empty.Description>
        </Empty.Header>
    </Empty.Root>
{:else}
    <Table.Toolbar>
        <Table.ToolbarSearch
            labelText="Search tasks"
            placeholder="Search by name, description or creator"
            bind:value={
                () => search,
                (v) => {
                    search = v;
                    syncUrl();
                }
            }
        />
        <div class="flex shrink-0 items-center gap-2 px-4">
            <Checkbox
                id={archivedId}
                bind:checked={
                    () => showArchived,
                    (v) => {
                        showArchived = v;
                        syncUrl();
                    }
                }
            />
            <Label
                for={archivedId}
                class="text-body-compact-01 text-text-primary"
            >
                Show archived
            </Label>
        </div>
    </Table.Toolbar>

    {#if visible.length === 0}
        <Empty.Root>
            <Empty.Header>
                {#if query}
                    <Empty.Title>No tasks match “{search.trim()}”</Empty.Title>
                    <Empty.Description>
                        {showArchived
                            ? "Try a different search term."
                            : "Try a different search term or select Show archived."}
                    </Empty.Description>
                {:else}
                    <Empty.Title>No active tasks</Empty.Title>
                    <Empty.Description>
                        Archived tasks are hidden. Select Show archived to see
                        them.
                    </Empty.Description>
                {/if}
            </Empty.Header>
        </Empty.Root>
    {:else}
        <Table.Root size="xl" aria-labelledby={headingId}>
            <Table.Header>
                <Table.Row>
                    <Table.Head>Task</Table.Head>
                    <Table.Head>Status</Table.Head>
                    <Table.Head>Creator</Table.Head>
                    <Table.Head>Progress</Table.Head>
                    <Table.Head><span class="sr-only">Actions</span></Table.Head
                    >
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each visible as t (t.id)}
                    <Table.Row>
                        <Table.Cell>
                            <a
                                href={resolve("/tasks/[taskid]", {
                                    taskid: String(t.id),
                                })}
                                class="text-link-primary hover:text-link-primary-hover hover:underline"
                            >
                                {t.name}
                            </a>
                            {#if t.description}
                                <p
                                    class="line-clamp-1 text-label-01 text-text-secondary"
                                >
                                    {t.description}
                                </p>
                            {/if}
                        </Table.Cell>
                        <Table.Cell>
                            {#if t.task_state}
                                {@const status = TASK_STATUS[t.task_state]}
                                <StatusIndicator
                                    icon={status.icon}
                                    iconClass={status.iconClass}
                                    label={status.label}
                                />
                            {:else}
                                —
                            {/if}
                        </Table.Cell>
                        <Table.Cell>{t.creator?.name ?? "—"}</Table.Cell>
                        <Table.Cell class="w-40">
                            {#if t.num_tasks > 0}
                                <ProgressBar
                                    labelText="Progress of {t.name}"
                                    hideLabel
                                    value={t.num_tasks_ready}
                                    max={t.num_tasks}
                                    helperText="{t.num_tasks_ready} / {t.num_tasks} ready"
                                />
                            {:else}
                                No subtasks
                            {/if}
                        </Table.Cell>
                        <Table.Cell class="table-xl:py-3">
                            <div class="flex justify-end">
                                <IconButton
                                    label="Edit"
                                    onclick={() => openEdit(t)}
                                >
                                    <Edit />
                                </IconButton>
                                <IconButton
                                    label="Delete"
                                    onclick={() => openDelete(t)}
                                >
                                    <TrashCan />
                                </IconButton>
                            </div>
                        </Table.Cell>
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    {/if}
{/if}

<Modal
    bind:open={editOpen}
    modalHeading="Edit task"
    modalLabel={editing?.name}
    primaryButtonText="Save"
    primaryButtonLoadingDescription="Saving…"
    successDescription="Saved"
    errorTitle="Task could not be saved"
    onsubmit={saveEdit}
>
    <div class="flex flex-col gap-6">
        <TextInput
            labelText="Name"
            bind:value={form.name}
            maxlength={256}
            invalidText={nameMissing && !form.name.trim()
                ? "Enter a task name"
                : undefined}
        />
        <TextArea
            labelText="Description (optional)"
            bind:value={form.description}
        />
        <SelectInput labelText="Status" bind:value={form.task_state}>
            {#if !form.task_state}
                <SelectItem value="" text="Choose a status" disabled />
            {/if}
            {#each TASK_STATES as state (state)}
                <SelectItem value={state} text={TASK_STATUS[state].label} />
            {/each}
        </SelectInput>
    </div>
</Modal>

<Modal
    bind:open={deleteOpen}
    danger
    size="xs"
    modalHeading="Delete task"
    modalLabel={deleting?.name}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Task could not be deleted"
    onsubmit={confirmDelete}
    onCloseAutoFocus={focusHeadingIfDeleted}
>
    {#if deleting}
        <p>{deleteBody(deleting)}</p>
    {/if}
</Modal>
