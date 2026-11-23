<!--
@component
Today's Image resolution block for the Measure tool: the µm per pixel in use and, under a disclosure, the X and Y fields and presets from the database or an ETDRS grid.
-->
<script lang="ts">
    import type { ETDRSCoordinates } from "$lib/types";
    import type { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import SetResolutionEtdrs from "$lib/viewer-window/panelMeasure/SetResolutionETDRS.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { getContext } from "svelte";
    import CommitNumberInput from "./CommitNumberInput.svelte";
    import { aiGrid, type GridLayers } from "./gridLayers.svelte";

    let { measure, grids }: { measure: MeasureTool; grids: GridLayers } =
        $props();

    const uid = $props.id();
    const { image } = getContext<ViewerContext>("viewerContext");
    const etdrsGrids = $derived(grids.list());
    const ai = aiGrid(image);
    let open = $state(false);
    let fraction = $state(0.85);
</script>

<div class="px-4 py-2">
    <p class="text-body-compact-01 text-text-primary tabular-nums">
        {measure.imageResX.toFixed(2)} × {measure.imageResY.toFixed(2)} µm/px
    </p>
    <h4>
        <button
            type="button"
            class="flex min-h-8 items-center gap-2 text-body-compact-01 text-text-primary hover:bg-layer-hover-01"
            aria-expanded={open}
            aria-controls={open ? `${uid}-body` : undefined}
            onclick={() => (open = !open)}
        >
            <ChevronRight
                class="shrink-0 transition-transform {open ? 'rotate-90' : ''}"
                aria-hidden="true"
            />
            Image resolution
        </button>
    </h4>
    {#if open}
        <div id="{uid}-body" class="flex flex-col items-start gap-2 pt-1">
            <CommitNumberInput
                labelText="X (µm/px)"
                value={measure.imageResX}
                step={0.1}
                oncommit={(v) => (measure.imageResX = v)}
            />
            <CommitNumberInput
                labelText="Y (µm/px)"
                value={measure.imageResY}
                step={0.1}
                oncommit={(v) => (measure.imageResY = v)}
            />
            {#if measure.dbResAvailable}
                <SetResolutionEtdrs
                    valueFixed={image.resolution.x}
                    measureTool={measure}
                    name="database"
                    {fraction}
                />
            {/if}
            <CommitNumberInput
                labelText="Fraction"
                value={fraction}
                step={0.01}
                min={0.01}
                max={1}
                oncommit={(v) => (fraction = v)}
            />
            {#if ai}
                <SetResolutionEtdrs
                    value={ai.form_data}
                    measureTool={measure}
                    name="AI grid"
                    {fraction}
                />
            {/if}
            {#each etdrsGrids as grid (grid.id)}
                <SetResolutionEtdrs
                    value={grid.form_data as ETDRSCoordinates}
                    measureTool={measure}
                    name="{grid.creator.name} [{grid.id}]"
                    {fraction}
                />
            {/each}
        </div>
    {/if}
</div>
