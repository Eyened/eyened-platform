<script lang="ts">
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import PaginatedResults from "$lib/components/PaginatedResults.svelte";
    import { Button } from "$lib/components/ui/button";
    import * as Table from "$lib/components/ui/table";
    import SubTaskRow from "$lib/tasks/SubTaskRow.svelte";
    import { updateSubTask } from "$lib/data/api";
    import { setContext } from "svelte";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";
    import { toast } from "svelte-sonner";

    let {
        rows,
        taskId,
        count,
        page,
        perPage = 20,
        onPageChange,
    }: {
        rows: SubTaskWithImagesGET[];
        taskId: number;
        count: number;
        page: number;
        perPage?: number;
        onPageChange: (p: number) => void;
    } = $props();

    const browserContext = new BrowserContext();
    setContext("browserContext", browserContext);

    const unassignedOnPage = $derived(
        rows.filter((r) => !(r as any).creator && !r.creator_id),
    );
    let claimingPage = $state(false);

    async function claimAllUnassignedOnPage() {
        if (unassignedOnPage.length === 0) return;
        claimingPage = true;
        let claimed = 0;
        let failed = 0;
        try {
            for (const row of unassignedOnPage) {
                try {
                    await updateSubTask(row.id, { claim: true });
                    claimed += 1;
                } catch {
                    failed += 1;
                }
            }
            if (failed === 0) {
                toast.success(`Claimed ${claimed} subtask(s)`);
            } else {
                toast.message(`Claimed ${claimed}, failed ${failed}`);
            }
        } finally {
            claimingPage = false;
        }
    }
</script>

<div class="mb-3 flex items-center gap-2">
    <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={claimingPage || unassignedOnPage.length === 0}
        onclick={claimAllUnassignedOnPage}
    >
        Claim all unassigned on this page
        {#if unassignedOnPage.length > 0}
            ({unassignedOnPage.length})
        {/if}
    </Button>
</div>

<PaginatedResults {count} {perPage} {page} {onPageChange}>
    <div class="rounded-md border">
        <Table.Root>
            <Table.Header>
                <Table.Row>
                    <Table.Head>ID</Table.Head>
                    <Table.Head>Status</Table.Head>
                    <Table.Head>Assignee</Table.Head>
                    <Table.Head>View</Table.Head>
                    <Table.Head>Images</Table.Head>
                    <Table.Head>Comments</Table.Head>
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each rows as row (row.id)}
                    <SubTaskRow subtask={row} {taskId} />
                {:else}
                    <Table.Row>
                        <Table.Cell colspan="6" class="h-24 text-center">
                            No results.
                        </Table.Cell>
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    </div>
</PaginatedResults>
