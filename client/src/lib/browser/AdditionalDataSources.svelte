<script lang="ts">
    import {
        loadDataSource,
        resolveURL,
        resolveValue,
    } from "$lib/browser/dataSources";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { untrack } from "svelte";
    import ExternalData from "./ExternalData.svelte";

    interface Props {
        context: any;
        additional_data_sources: AdditionalDataSource[];
    }
    let { context, additional_data_sources }: Props = $props();

    type AdditionalDataSource = {
        name: string;
        url: string;
        conditions: { parameter: string; value: string | string[] }[];
        collapse?: boolean;
    };

    function condition_applies(
        condition: AdditionalDataSource["conditions"][number],
    ) {
        const value = resolveValue(condition.parameter, context);
        if (Array.isArray(condition.value)) {
            return condition.value.includes(value);
        }
        return condition.value === value;
    }
    const sources = $derived(
        additional_data_sources.filter((s) =>
            s.conditions.every(condition_applies),
        ),
    );
    // One accordion item per source; v1's per-source `collapse` sets whether it starts closed.
    let open = $state(
        untrack(() => sources.filter((s) => !s.collapse).map((s) => s.name)),
    );
</script>

{#if sources.length > 0}
    <!-- ASSUMPTION: source names are unique in the extensions config. -->
    <Accordion.Root bind:value={open} class="mt-4">
        {#each sources as source (source.name)}
            <!-- The await depends on the URL string only, so a study update that leaves the URL alone does not reload. -->
            {@const url = resolveURL(source.url, context)}
            <Accordion.Item value={source.name}>
                <Accordion.Trigger>{source.name}</Accordion.Trigger>
                <Accordion.Content>
                    {#await loadDataSource(url)}
                        <InlineLoading status="active" description="Loading…" />
                    {:then data}
                        <ExternalData {data} />
                    {:catch}
                        <!-- The error names the URL, which can hold a patient identifier. -->
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
