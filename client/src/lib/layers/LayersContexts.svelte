<!--
@component
Provides the selected viewport's viewer and segmentation contexts to the sections below, which read them like the old per-viewport panels did.
-->
<script lang="ts">
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import { setContext, untrack } from "svelte";
    import type { LayerSectionId } from "./layerSections";
    import EtdrsSection from "./EtdrsSection.svelte";
    import SegmentationsSection from "./SegmentationsSection.svelte";

    let {
        target,
        sections,
        shown,
        open,
        ontoggle,
    }: {
        target: LayersTarget;
        sections: LayerSectionId[];
        shown: boolean;
        open: Record<LayerSectionId, boolean>;
        ontoggle: (id: LayerSectionId) => void;
    } = $props();

    // The panel keys this component on the target, so the first value is the only one.
    const { viewerContext, mainViewerContext } = untrack(() => target);
    setContext("viewerContext", viewerContext);
    setContext("mainViewerContext", mainViewerContext);
</script>

{#if sections.includes("segmentations")}
    <SegmentationsSection
        open={open.segmentations}
        ontoggle={() => ontoggle("segmentations")}
        {shown}
    />
{/if}
{#if sections.includes("etdrs")}
    <EtdrsSection
        grids={target.grids}
        open={open.etdrs}
        ontoggle={() => ontoggle("etdrs")}
        {shown}
    />
{/if}
