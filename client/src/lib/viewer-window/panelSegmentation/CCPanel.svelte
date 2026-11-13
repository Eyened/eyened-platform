<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";

    let { segmentationItem }: { segmentationItem: SegmentationItem } = $props();

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const uid = $props.id();

    const on = $derived(
        mainViewerContext.applyConnectedComponents.has(segmentationItem),
    );
</script>

<Field.Field orientation="horizontal">
    <Toggle
        id="{uid}-cc"
        bind:checked={
            () => on,
            () => mainViewerContext.toggleConnectedComponents(segmentationItem)
        }
    />
    <Field.Label for="{uid}-cc" class="text-body-compact-01 text-text-primary"
        >Connected components</Field.Label
    >
</Field.Field>
