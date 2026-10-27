<script lang="ts">
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { fetchInstance } from "$lib/data/api";
    import { instances } from "$lib/data/stores.svelte";
    import InstanceInfo from "./InstanceInfo.svelte";

    let { instanceId }: { instanceId: string } = $props();

    const loading = fetchInstance(instanceId);
    const instance = $derived(instances.get(instanceId));
</script>

{#await loading}
    <InlineLoading status="active" description="Loading image information…" />
{:then}
    {#if instance}
        <InstanceInfo {instanceId} />
    {:else}
        <InlineNotification title="Image not found" />
    {/if}
{:catch error}
    <InlineNotification
        title="Image information could not be loaded"
        subtitle={error instanceof Error ? error.message : String(error)}
    />
{/await}
