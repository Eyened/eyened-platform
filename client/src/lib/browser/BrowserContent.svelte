<script lang="ts">
    import { browserExtensions } from "$lib/extensions";
    
    import { data } from "$lib/datamodel/model";
    import { derived } from "svelte/store";
    import InstancesTable from "./InstancesTable.svelte";
    import StudyBlock from "./StudyBlock.svelte";

    interface Props {
        renderMode?: "studies" | "instances";
        mode?: "full" | "overlay";
    }

    let { renderMode = "studies", mode = "full" }: Props = $props();

    const { instances, studies } = data;

    // getting studies from instances rather than from model directly
    const sorted_studies = derived(studies, (studies) => {
        // const studies = new Set<Study>($instances.map((i) => i.study));
        return [...studies].sort((a, b) => b.date - a.date);
    });

    // TODO implement pagination
</script>

{#if renderMode == "instances"}
    {#if $instances.length}
        <InstancesTable instances={$instances} />
    {:else}
        <div class="no-content">No images found</div>
    {/if}
{:else if $sorted_studies.length}
    {#each $sorted_studies as study (study)}
        <StudyBlock {study} {mode} />
    {/each}
    {#if mode == "full"}
        {#each browserExtensions as extension}
            <extension.component {...extension.props} />
        {/each}
    {/if}
{:else}
    <div class="no-content">No studies found</div>
{/if}

<style>
    div.no-content {
        display: flex;
        flex-direction: column;
        flex: 1;
    }
</style>
