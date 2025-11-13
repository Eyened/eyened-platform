<script lang="ts">
    import { loadDataSource, resolveURL, resolveValue } from "$lib/browser/dataSources";
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
    async function loadAdditionalData(source: AdditionalDataSource) {
        const url = resolveURL(source.url, context);
        return loadDataSource(url);
    }
</script>

<div>
    {#each additional_data_sources as source}
        {#if source.conditions.every(condition_applies)}
            <div>
                {#await loadAdditionalData(source)}
                    <div>Loading...</div>
                {:then data}
                    <ExternalData
                        {data}
                        name={source.name}
                        collapse={source.collapse}
                    />
                {:catch error}
                    <div>Error: {error}</div>
                {/await}
            </div>
        {/if}
    {/each}
</div>
