<script lang="ts">
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import * as Table from "$lib/components/ui/table/index.js";
    import { setContext } from "svelte";
    import type { SvelteSet } from "svelte/reactivity";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";
    import SubtaskCommentsModal from "./SubtaskCommentsModal.svelte";
    import SubTaskRow from "./SubTaskRow.svelte";

    type Props = {
        rows: SubTaskWithImagesGET[];
        taskId: number;
        headingId: string;
        /** Owned by the page, which clears it on a filter or page change. */
        expanded: SvelteSet<number>;
        /** A filter or page change is loading: skeleton rows under the real header. */
        loading?: boolean;
        onerror: (title: string, subtitle?: string) => void;
        onchange: () => void;
    };
    let {
        rows,
        taskId,
        headingId,
        expanded,
        loading = false,
        onerror,
        onchange,
    }: Props = $props();

    // Thumbnails read their size and selection from a browser context.
    setContext("browserContext", new BrowserContext());

    const allExpanded = $derived(
        rows.length > 0 && rows.every((r) => expanded.has(r.id)),
    );

    function toggleAll() {
        if (allExpanded) expanded.clear();
        else for (const r of rows) expanded.add(r.id);
    }

    function toggle(id: number) {
        if (expanded.has(id)) expanded.delete(id);
        else expanded.add(id);
    }

    let editing = $state<SubTaskWithImagesGET | null>(null);
    let editOpen = $state(false);
    let returnFocus: HTMLElement | null = null;

    function openComments(subtask: SubTaskWithImagesGET, button: HTMLElement) {
        editing = subtask;
        returnFocus = button;
        editOpen = true;
    }

    // A save assigns the set, so a page filtered by assignee can drop its row.
    function focusHeadingIfGone(event: Event) {
        if (!returnFocus?.isConnected) {
            event.preventDefault();
            document.getElementById(headingId)?.focus();
        }
    }
</script>

<Table.Root size="lg" aria-labelledby={headingId}>
    <Table.Header>
        <Table.Row>
            <Table.Head id="{headingId}-expand" class="w-10 ps-2 pe-0">
                <Table.ExpandButton
                    expanded={allExpanded}
                    ontoggle={toggleAll}
                    aria-label={allExpanded
                        ? "Collapse all rows"
                        : "Expand all rows"}
                />
            </Table.Head>
            <Table.Head>Set</Table.Head>
            <Table.Head>Status</Table.Head>
            <Table.Head>Assignee</Table.Head>
            <Table.Head>Images</Table.Head>
            <Table.Head>Comments</Table.Head>
            <Table.Head><span class="sr-only">Actions</span></Table.Head>
        </Table.Row>
    </Table.Header>
    <Table.Body>
        {#if loading}
            <Table.SkeletonRows columns={7} />
        {:else}
            {#each rows as row (row.id)}
                <SubTaskRow
                    subtask={row}
                    {taskId}
                    {headingId}
                    expanded={expanded.has(row.id)}
                    ontoggle={() => toggle(row.id)}
                    onedit={openComments}
                    {onerror}
                    {onchange}
                />
            {/each}
        {/if}
    </Table.Body>
</Table.Root>

<SubtaskCommentsModal
    bind:open={editOpen}
    subtask={editing}
    {onchange}
    onCloseAutoFocus={focusHeadingIfGone}
/>
