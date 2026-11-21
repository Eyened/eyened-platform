<script lang="ts">
    import { untrack } from "svelte";
    import { DataSourceError, loadDataSource } from "$lib/browser/dataSources";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import type { StudyGET } from "../../types/openapi_types";
    import ExternalData from "./ExternalData.svelte";

    let { study }: { study: StudyGET } = $props();

    // One accordion item per source; the server's `collapse` sets whether it starts closed.
    let open = $state(
        untrack(() =>
            study.data_sources.filter((s) => !s.collapse).map((s) => s.name),
        ),
    );
</script>

{#if study.data_sources.length > 0}
    <!-- -mx-4 cancels the tile padding (Carbon Accordion, Flush alignment). -->
    <Accordion.Root bind:value={open} class="-mx-4 mt-4">
        {#each study.data_sources as source (source.name)}
            <Accordion.Item value={source.name}>
                <Accordion.Trigger>{source.name}</Accordion.Trigger>
                <Accordion.Content>
                    {#await loadDataSource(study.id, source.name)}
                        <InlineLoading status="active" description="Loading…" />
                    {:then data}
                        <ExternalData {data} />
                    {:catch error}
                        {#if error instanceof DataSourceError && error.status === 404}
                            <p class="px-4 text-label-01 text-text-secondary">
                                No data for this study.
                            </p>
                        {:else}
                            <InlineNotification
                                title="{source.name} could not be loaded"
                                subtitle="Try again later."
                            />
                        {/if}
                    {/await}
                </Accordion.Content>
            </Accordion.Item>
        {/each}
    </Accordion.Root>
{/if}
