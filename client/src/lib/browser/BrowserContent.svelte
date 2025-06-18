<script lang="ts">
    import { data } from "$lib/datamodel/model";
    import InstancesTable from "./InstancesTable.svelte";
    import Patient from "./Patient.svelte";

    interface Props {
        renderMode?: "studies" | "images";
        mode?: "full" | "overlay";
    }

    let { renderMode = "studies", mode = "full" }: Props = $props();

    const { instances, patients } = data;
</script>

{#if renderMode == "images"}
    {#if $instances.length}
        <InstancesTable instances={$instances} />
    {:else}
        <div class="no-content">No images found</div>
    {/if}
{:else if $patients.length}
    {#each $patients as patient}
        <Patient {patient} {mode} />
    {/each}
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
