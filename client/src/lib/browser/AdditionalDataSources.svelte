<script lang="ts">
    import {
        isTablesContribution,
        listDataSources,
        loadDataSource,
    } from "$lib/browser/dataSources";
    import {
        readOpenExtensionNames,
        writeOpenExtensionNames,
    } from "$lib/browser/openExtensionPrefs";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import type { DataSourceGET } from "../../types/openapi_types";
    import ExternalData from "./ExternalData.svelte";

    let { studyId }: { studyId: number } = $props();

    let sources = $state<DataSourceGET[]>([]);
    let open = $state<string[]>([]);

    $effect(() => {
        let cancelled = false;
        listDataSources(studyId)
            .then((result) => {
                if (cancelled) return;
                sources = result;
                open = readOpenExtensionNames(result.map((s) => s.name));
            })
            .catch(() => {
                if (!cancelled) sources = [];
            });
        return () => {
            cancelled = true;
        };
    });

    $effect(() => {
        if (sources.length > 0) writeOpenExtensionNames(open);
    });
</script>

{#if sources.length > 0}
    <!-- -mx-4 cancels the tile padding (Carbon Accordion, Flush alignment). -->
    <Accordion.Root bind:value={open} class="-mx-4 mt-4">
        {#each sources as source (source.name)}
            <Accordion.Item value={source.name}>
                <Accordion.Trigger>{source.name}</Accordion.Trigger>
                <Accordion.Content>
                    {#await loadDataSource(studyId, source.name)}
                        <InlineLoading status="active" description="Loading…" />
                    {:then data}
                        {#if isTablesContribution(data)}
                            <ExternalData groups={data.groups} />
                        {:else}
                            <InlineNotification
                                title="{source.name} could not be loaded"
                                subtitle="Try again later."
                            />
                        {/if}
                    {:catch}
                        <InlineNotification
                            title="{source.name} could not be loaded"
                            subtitle="Try again later."
                        />
                    {/await}
                </Accordion.Content>
            </Accordion.Item>
        {/each}
    </Accordion.Root>
{/if}
