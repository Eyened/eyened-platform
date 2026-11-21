<!--
@component
The selected item's options under the Layers list: a fixed header, then a scrolling body. Nothing selected says what to do.
-->
<script lang="ts">
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import PaneHeader from "./pane/PaneHeader.svelte";

    let { target }: { target: LayersTarget } = $props();
    const uid = $props.id();
    const selected = $derived(target.selection.value);
</script>

{#if !selected}
    <p class="px-4 py-3 text-body-compact-01 text-text-secondary">
        Select a layer to see its options.
    </p>
{:else}
    <section aria-labelledby="{uid}-name" class="flex min-h-0 flex-1 flex-col">
        {#if selected.kind === "segmentation"}
            <PaneHeader
                id="{uid}-name"
                name={selected.item.segmentation.feature.name}
                type="Segmentation · {selected.item.segmentation
                    .data_representation}"
            />
        {:else if selected.kind === "grid"}
            <PaneHeader id="{uid}-name" name="ETDRS grid" type="ETDRS grid" />
        {:else if selected.kind === "pointset"}
            <PaneHeader
                id="{uid}-name"
                name="Registration [{selected.id}]"
                type="Pointset"
            />
        {:else}
            <PaneHeader id="{uid}-name" name="Line" type="Distance line" />
        {/if}
    </section>
{/if}
