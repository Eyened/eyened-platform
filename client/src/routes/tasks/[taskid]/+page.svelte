<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { page as appPage } from "$app/state";
    import { ApiError } from "$lib/api/client";
    import Main from "$lib/components/Main.svelte";
    import * as Breadcrumb from "$lib/components/ui/breadcrumb/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { StatusIndicator } from "$lib/components/ui/status-indicator/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import {
        fetchSubTaskAssignees,
        fetchSubTasks,
        fetchTask,
        updateSubTask,
    } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { subtasks, tasks } from "$lib/data/stores.svelte";
    import SubtasksTable from "$lib/tasks/SubtasksTable.svelte";
    import { SUBTASK_STATES, SUBTASK_STATUS } from "$lib/tasks/subtaskStatus";
    import { TASK_STATUS } from "$lib/tasks/taskStatus";
    import { cn } from "$lib/utils.js";
    import { getContext, onDestroy, onMount, tick } from "svelte";
    import { SvelteSet } from "svelte/reactivity";
    import type { SubTaskWithImagesGET } from "../../../types/openapi_types";

    let { data } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const headingId = "task-heading";
    const PAGE_SIZES = [10, 20, 50, 100];
    const HEADERS = ["", "Set", "Status", "Assignee", "Images", "Comments", ""];
    const me = String(globalContext.user.id);

    // Filters and page from the URL, read once. v1's parameter names; `page` is 0-based.
    // Dropdown ids: status "all" or a SubTaskState; assignee "all", "unassigned", "me" or a creator id.
    const params = appPage.url.searchParams;
    const statusParam = params.get("status") ?? "";
    let status = $state(
        (SUBTASK_STATES as string[]).includes(statusParam)
            ? statusParam
            : "all",
    );
    let assignee = $state(initialAssignee());
    const pageParam = params.get("page") ?? "";
    let pageIndex = $state(/^\d+$/.test(pageParam) ? Number(pageParam) : 0);
    const limitParam = Number(params.get("limit"));
    let limit = $state(PAGE_SIZES.includes(limitParam) ? limitParam : 20);

    function initialAssignee(): string {
        const unassigned = params.get("unassigned");
        if (unassigned === "1" || unassigned === "true") return "unassigned";
        const creator = params.get("creator_id") ?? "";
        if (!/^[1-9]\d*$/.test(creator)) return "all";
        return creator === me ? "me" : creator;
    }

    const filtered = $derived(status !== "all" || assignee !== "all");

    const task = $derived(
        data.taskid === null ? undefined : tasks.get(data.taskid),
    );
    let ready = $state(false);
    // "" when there is no server message (an id that is not a number).
    let loadError = $state<string | null>(null);

    // fetchSubTasks merges every response into the global store, so list this page's ids only.
    let rowIds = $state<number[]>([]);
    const rows = $derived(
        rowIds.flatMap((id) => {
            const s = subtasks.get(id);
            return s ? [s] : [];
        }),
    );
    let count = $state(0);
    let loading = $state(false);
    let request = 0;
    const expanded = new SvelteSet<number>();

    let assignees = $state<{ id: number; name: string }[]>([]);

    type Notice = { title: string; subtitle?: string };
    let notice = $state<Notice | null>(null);
    const message = (e: unknown) =>
        e instanceof Error ? e.message : String(e);

    const statusItems = [
        { id: "all", text: "All statuses" },
        ...SUBTASK_STATES.map((s) => ({
            id: s,
            text: SUBTASK_STATUS[s].label,
        })),
    ];
    const assigneeItems = $derived.by(() => {
        const items = [
            { id: "all", text: "All assignees" },
            { id: "unassigned", text: "Unassigned" },
            { id: "me", text: "Assigned to me" },
            ...assignees
                .filter((a) => String(a.id) !== me)
                .map((a) => ({ id: String(a.id), text: a.name })),
        ];
        // An id from the URL that the list lacks (load failed, no sets) still gets a label.
        if (!items.some((i) => i.id === assignee)) {
            items.push({ id: assignee, text: `Assignee #${assignee}` });
        }
        return items;
    });

    function query() {
        return {
            task_id: data.taskid as number,
            with_images: true,
            limit,
            page: pageIndex,
            subtask_status: status === "all" ? undefined : status,
            unassigned: assignee === "unassigned" ? true : undefined,
            creator_id:
                assignee === "all" || assignee === "unassigned"
                    ? undefined
                    : Number(assignee === "me" ? me : assignee),
        };
    }

    function syncUrl() {
        // Built without mutation: svelte/prefer-svelte-reactivity flags a mutated URLSearchParams.
        const entries: [string, string][] = [
            ["page", String(pageIndex)],
            ["limit", String(limit)],
        ];
        if (status !== "all") entries.push(["status", status]);
        if (assignee === "unassigned") entries.push(["unassigned", "1"]);
        else if (assignee !== "all")
            entries.push(["creator_id", assignee === "me" ? me : assignee]);
        // Same route (/tasks/[taskid]), only the query string changes;
        // the route id is statically known here so resolve() applies.
        goto(
            resolve(`/tasks/[taskid]?${new URLSearchParams(entries)}`, {
                taskid: String(data.taskid),
            }),
            { replaceState: true, keepFocus: true, noScroll: true },
        );
    }

    // Applies a response only if no newer request was sent. A page past the end
    // (`?page=500`) refetches the last page once.
    async function loadSubtasks(): Promise<void> {
        const id = ++request;
        const current = () => id === request;
        try {
            let res = await fetchSubTasks(query());
            const last = Math.max(0, Math.ceil(res.count / limit) - 1);
            if (current() && pageIndex > last) {
                pageIndex = last;
                res = await fetchSubTasks(query());
            }
            if (!current()) return;
            rowIds = res.subtasks.map((s: SubTaskWithImagesGET) => s.id);
            count = res.count;
            syncUrl();
        } catch (e) {
            if (current()) throw e;
        } finally {
            if (current()) loading = false;
        }
    }

    // A failure keeps the fixed items (All, Unassigned, Assigned to me), as in v1.
    async function loadAssignees() {
        try {
            assignees = await fetchSubTaskAssignees(data.taskid as number);
        } catch (e) {
            console.error("Failed to load assignees", e);
        }
    }

    // A filter or page change: skeleton rows, rows collapsed, the notification cleared.
    async function reload() {
        notice = null;
        expanded.clear();
        loading = true;
        try {
            await loadSubtasks();
        } catch (e) {
            notice = {
                title: "Subtasks could not be loaded",
                subtitle: message(e),
            };
        }
    }

    // After an action: the old rows stay until the new ones arrive; assignees reload too.
    async function refresh() {
        const active = document.activeElement;
        loadAssignees();
        try {
            await loadSubtasks();
        } catch (e) {
            notice = {
                title: "Subtasks could not be loaded",
                subtitle: message(e),
            };
        }
        // The refresh may remove the focused row (claim under "Unassigned"); keep focus on the page.
        await tick();
        if (active instanceof HTMLElement && !active.isConnected) {
            document.getElementById(headingId)?.focus();
        }
    }

    function rowChanged() {
        notice = null;
        refresh();
    }

    function rowFailed(title: string, subtitle?: string) {
        notice = { title, subtitle };
        refresh();
    }

    function selectStatus(id: string) {
        status = id;
        pageIndex = 0;
        reload();
    }

    function selectAssignee(id: string) {
        assignee = id;
        pageIndex = 0;
        reload();
    }

    function changePage(p: { page: number; pageSize: number }) {
        pageIndex = p.page - 1;
        limit = p.pageSize;
        reload();
    }

    const unassignedOnPage = $derived(
        rows.filter((r) => r.creator_id == null && !r.creator),
    );
    let claiming = $state(false);

    async function claimAll() {
        if (claiming || loading || unassignedOnPage.length === 0) return;
        claiming = true;
        notice = null;
        const targets = [...unassignedOnPage];
        let claimed = 0;
        let lastError: unknown = null;
        for (const row of targets) {
            try {
                await updateSubTask(row.id, { claim: true });
                claimed += 1;
            } catch (e) {
                if (
                    e instanceof ApiError &&
                    e.code === "subtask_already_claimed"
                )
                    continue;
                lastError = e;
            }
        }
        if (lastError !== null) {
            notice = {
                title: `Claimed ${claimed} of ${targets.length} sets`,
                subtitle: message(lastError),
            };
        }
        await refresh();
        claiming = false;
    }

    // Invalidates in-flight responses, so none navigates after unmount.
    onDestroy(() => {
        request += 1;
    });

    onMount(async () => {
        if (data.taskid === null) {
            loadError = "";
            return;
        }
        loadAssignees();
        try {
            await Promise.all([fetchTask(data.taskid), loadSubtasks()]);
            ready = true;
        } catch (e) {
            loadError = message(e);
        }
    });
</script>

<Main>
    <Breadcrumb.Root class="mt-8">
        <Breadcrumb.List>
            <Breadcrumb.Item>
                <Breadcrumb.Link href={resolve("/tasks")}>Tasks</Breadcrumb.Link
                >
            </Breadcrumb.Item>
        </Breadcrumb.List>
    </Breadcrumb.Root>

    {#if loadError !== null}
        <InlineNotification
            class="mt-6"
            title="Task could not be loaded"
            subtitle={loadError || undefined}
        />
    {:else if !ready || !task}
        <span class={cn(Table.skeleton, "mt-2 mb-6 h-6 w-40")}></span>
        <Table.Skeleton size="lg" headers={HEADERS} />
    {:else}
        <div class="mt-2 mb-6">
            <div class="flex items-center gap-4">
                <!-- tabindex=-1: focus lands here when a row it came from is gone -->
                <h1
                    id={headingId}
                    tabindex="-1"
                    class="text-heading-04 text-text-primary"
                >
                    {task.name}
                </h1>
                {#if task.task_state}
                    {@const s = TASK_STATUS[task.task_state]}
                    <StatusIndicator
                        icon={s.icon}
                        iconClass={s.iconClass}
                        label={s.label}
                    />
                {/if}
            </div>
            {#if task.description}
                <p class="mt-2 text-body-01 text-text-secondary">
                    {task.description}
                </p>
            {/if}
        </div>

        {#if notice}
            <InlineNotification
                class="mb-4"
                title={notice.title}
                subtitle={notice.subtitle}
            />
        {/if}

        {#if count === 0 && !loading && !filtered}
            <Empty.Root>
                <Empty.Header>
                    <Empty.Title>This task has no subtasks</Empty.Title>
                </Empty.Header>
            </Empty.Root>
        {:else}
            <Table.Toolbar>
                <div class="flex h-full items-center gap-4 ps-4">
                    <Dropdown
                        type="inline"
                        labelText="Status"
                        items={statusItems}
                        selectedId={status}
                        onselect={selectStatus}
                    />
                    <Dropdown
                        type="inline"
                        labelText="Assignee"
                        items={assigneeItems}
                        selectedId={assignee}
                        onselect={selectAssignee}
                    />
                </div>
                <Button
                    size="lg"
                    class="ms-auto"
                    aria-disabled={claiming ||
                        loading ||
                        unassignedOnPage.length === 0 ||
                        undefined}
                    onclick={claimAll}
                >
                    Claim unassigned on page
                </Button>
            </Table.Toolbar>

            {#if count === 0 && !loading}
                <Empty.Root>
                    <Empty.Header>
                        <Empty.Title
                            >No subtasks match these filters</Empty.Title
                        >
                        <Empty.Description>
                            Select a different status or assignee.
                        </Empty.Description>
                    </Empty.Header>
                </Empty.Root>
            {:else}
                <SubtasksTable
                    {rows}
                    taskId={task.id}
                    {headingId}
                    {expanded}
                    {loading}
                    onerror={rowFailed}
                    onchange={rowChanged}
                />
                <Table.Pagination
                    page={pageIndex + 1}
                    pageSize={limit}
                    pageSizes={PAGE_SIZES}
                    totalItems={count}
                    onchange={changePage}
                />
            {/if}
        {/if}
    {/if}
</Main>
