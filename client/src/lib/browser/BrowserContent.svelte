<script lang="ts">
    import InstancesTable from "./InstancesTable.svelte";
    import type { Instance } from "$lib/datamodel/instance.svelte.ts";
    import type { Patient } from "$lib/datamodel/patient.ts";
    import PatientComponent from "./PatientComponent.svelte";

    interface Props {
        instances: Instance[];
        patients: Patient[];
        renderMode?: "studies" | "images";
        mode?: "full" | "overlay";
    }

    let {
        instances,
        patients,
        renderMode = "studies",
        mode = "full",
    }: Props = $props();
    
</script>

{#if renderMode == "images"}
    {#if instances.length}
        <InstancesTable {instances} />
    {:else}
        <div class="no-content">No images found</div>
    {/if}
{:else if patients.length}
    {#each patients as patient}
        <PatientComponent {patient} {mode} />
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
