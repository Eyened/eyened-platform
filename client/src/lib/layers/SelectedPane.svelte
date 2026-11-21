<!--
@component
The selected item's options under the Layers list: a fixed header, then a scrolling body. Nothing selected says what to do.
-->
<script lang="ts">
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import GridPane from "./pane/GridPane.svelte";
    import LinePane from "./pane/LinePane.svelte";
    import PointsetPane from "./pane/PointsetPane.svelte";
    import SegmentationPane from "./pane/SegmentationPane.svelte";

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
            {#key selected.item}
                <SegmentationPane id="{uid}-name" item={selected.item} />
            {/key}
        {:else if selected.kind === "grid"}
            <GridPane id="{uid}-name" gridId={selected.id} />
        {:else if selected.kind === "pointset"}
            <PointsetPane id="{uid}-name" pointsetId={selected.id} />
        {:else}
            <LinePane
                id="{uid}-name"
                line={selected.line}
                lines={selected.lines}
                scale={target.scale}
            />
        {/if}
    </section>
{/if}
