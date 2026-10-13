<script lang="ts">
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import InstanceComponent from "./InstanceComponent.svelte";
    import StudyBlock from "./StudyBlock.svelte";

    // Empty states, results (styled in PR 5) and one Pagination below them.
    const browserContext = getContext<BrowserContext>("browserContext");
    let { mode = "full" }: { mode?: "full" | "overlay" } = $props();

    const imagesMode = $derived(
        browserContext.queryMode === "instances" &&
            browserContext.displayMode === "instance",
    );

    function changePage(p: { page: number; pageSize: number }) {
        if (p.pageSize !== browserContext.limit)
            browserContext.setPageSize(p.pageSize);
        else browserContext.setPage(p.page - 1);
    }
</script>

{#if !browserContext.hasSearched}
    <Empty.Root>
        <Empty.Header>
            <Empty.Title>Search for images</Empty.Title>
            <Empty.Description>
                Fill in the filters, then select Search.
            </Empty.Description>
        </Empty.Header>
    </Empty.Root>
{:else if browserContext.failed}
    <!-- The notification in the search form says what failed. -->
{:else if browserContext.count === 0}
    {#if !browserContext.loading}
        <Empty.Root>
            <Empty.Header>
                <Empty.Title>No results found</Empty.Title>
                <Empty.Description>
                    Change or remove filters, then search again.
                </Empty.Description>
            </Empty.Header>
        </Empty.Root>
    {/if}
{:else}
    <div aria-busy={browserContext.loading || undefined} class="py-4">
        {#if imagesMode}
            <div class="flex flex-wrap gap-2">
                {#each browserContext.orderedInstances as instance (instance.id)}
                    <InstanceComponent {instance} />
                {/each}
            </div>
        {:else}
            {#each browserContext.orderedStudies as study (study.id)}
                <StudyBlock {study} {mode} />
            {/each}
        {/if}
    </div>
    <Table.Pagination
        class="border-t border-border-subtle-01 in-dialog:border-border-subtle-02"
        page={browserContext.page + 1}
        pageSize={browserContext.limit}
        pageSizes={browserContext.limitOptions}
        totalItems={browserContext.count}
        onchange={changePage}
    />
{/if}
