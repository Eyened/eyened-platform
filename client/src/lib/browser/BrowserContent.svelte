<script lang="ts">
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { skeleton } from "$lib/components/ui/table/skeleton.js";
    import { cn } from "$lib/utils.js";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import InstanceComponent from "./InstanceComponent.svelte";
    import SkeletonStudyBlock from "./SkeletonStudyBlock.svelte";
    import StudyBlock from "./StudyBlock.svelte";

    // Empty states, skeletons, results and one Pagination below them.
    const browserContext = getContext<BrowserContext>("browserContext");

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
{:else}
    {#if browserContext.loading}
        <!-- Carbon Loading, progressive: every search, page and page-size change shows skeletons. -->
        <div aria-busy="true" class="py-4">
            {#if imagesMode}
                <div class="flex gap-2 overflow-hidden">
                    {#each { length: 12 }, i (i)}
                        <span
                            class={cn(skeleton, "shrink-0")}
                            style="width: calc({browserContext.thumbnailSize} + 2px); height: calc({browserContext.thumbnailSize} + 2rem + 2px);"
                        ></span>
                    {/each}
                </div>
            {:else}
                <div class="flex flex-col gap-4">
                    {#each { length: 3 }, i (i)}
                        <SkeletonStudyBlock />
                    {/each}
                </div>
            {/if}
        </div>
    {:else if browserContext.count === 0}
        <Empty.Root>
            <Empty.Header>
                <Empty.Title>No results found</Empty.Title>
                <Empty.Description>
                    Change or remove filters, then search again.
                </Empty.Description>
            </Empty.Header>
        </Empty.Root>
    {:else}
        <div class="py-4">
            {#if imagesMode}
                <div class="flex flex-wrap gap-2">
                    {#each browserContext.orderedInstances as instance (instance.id)}
                        <InstanceComponent {instance} />
                    {/each}
                </div>
            {:else}
                <div class="flex flex-col gap-4">
                    {#each browserContext.orderedStudies as study (study.id)}
                        <StudyBlock {study} />
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
    {#if browserContext.count > 0}
        <Table.Pagination
            class="border-t border-border-subtle-01 in-dialog:border-border-subtle-02"
            page={browserContext.page + 1}
            pageSize={browserContext.limit}
            pageSizes={browserContext.limitOptions}
            totalItems={browserContext.count}
            onchange={changePage}
        />
    {/if}
{/if}
