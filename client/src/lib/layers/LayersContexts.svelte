<!--
@component
Provides the selected viewport's viewer and segmentation contexts to the sections below, which read them like the old per-viewport panels did.
-->
<script lang="ts">
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import { setContext, untrack } from "svelte";
    import type { LayerSectionId } from "./layerSections";
    import BlendSection from "./BlendSection.svelte";
    import DistanceSection from "./DistanceSection.svelte";
    import EtdrsSection from "./EtdrsSection.svelte";
    import LocalizerSection from "./LocalizerSection.svelte";
    import PointsetsSection from "./PointsetsSection.svelte";
    import RegistrationSection from "./RegistrationSection.svelte";
    import ProjectionSection from "./ProjectionSection.svelte";
    import PaneLayout from "./PaneLayout.svelte";
    import SegmentationsSection from "./SegmentationsSection.svelte";

    let {
        target,
        sections,
        shown,
        open,
        ontoggle,
        withPane = false,
    }: {
        target: LayersTarget;
        sections: LayerSectionId[];
        shown: boolean;
        open: Record<LayerSectionId, boolean>;
        ontoggle: (id: LayerSectionId) => void;
        /** The Layers tab: the list sits above the Selected pane. */
        withPane?: boolean;
    } = $props();

    // The panel keys this component on the target, so the first value is the only one.
    const { viewerContext, mainViewerContext } = untrack(() => target);
    setContext("viewerContext", viewerContext);
    setContext("mainViewerContext", mainViewerContext);
</script>

{#snippet list()}
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
            scale={target.scale}
        />
    {/if}
    {#if sections.includes("pointsets")}
        <PointsetsSection
            open={open.pointsets}
            ontoggle={() => ontoggle("pointsets")}
        />
    {/if}
    {#if sections.includes("registration")}
        <RegistrationSection
            open={open.registration}
            ontoggle={() => ontoggle("registration")}
        />
    {/if}
    {#if sections.includes("blend")}
        <BlendSection
            blend={target.blend}
            open={open.blend}
            ontoggle={() => ontoggle("blend")}
        />
    {/if}
    {#if sections.includes("distance")}
        <DistanceSection
            distance={target.distance}
            scale={target.scale}
            open={open.distance}
            ontoggle={() => ontoggle("distance")}
        />
    {/if}
    {#if sections.includes("projection")}
        <ProjectionSection
            sources={target.projectionSources}
            open={open.projection}
            ontoggle={() => ontoggle("projection")}
        />
    {/if}
    {#if sections.includes("localizer")}
        <LocalizerSection
            localizer={target.localizer}
            open={open.localizer}
            ontoggle={() => ontoggle("localizer")}
        />
    {/if}
{/snippet}

{#if withPane}
    <PaneLayout {target}>{@render list()}</PaneLayout>
{:else}
    {@render list()}
{/if}
