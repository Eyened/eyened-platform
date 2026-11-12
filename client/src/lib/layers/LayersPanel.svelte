<!--
@component
The Layers panel body: the selected viewport's name, then the sections that apply to its image.
-->
<script lang="ts">
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { formSchemasByName } from "$lib/data";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext } from "svelte";
    import LayersContexts from "./LayersContexts.svelte";
    import { layerSections, type LayerSectionId } from "./layerSections";

    let {
        subtitle,
        shown,
    }: {
        /** "Viewport n · title". */
        subtitle: string;
        /** True while the panel is on screen. */
        shown: boolean;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const hide = mergeClientConfig(
        CLIENT_DEFAULTS,
        taskContext?.task.task_definition.config,
    ).layout.hide;

    const target = $derived(workspace.selectedViewport?.layers ?? null);
    const sections = $derived(
        target
            ? layerSections({
                  is2D: target.viewerContext.image.is2D,
                  hasEtdrsSchema: formSchemasByName.has(
                      BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID,
                  ),
                  hasRegistrationSchema: formSchemasByName.has(
                      BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
                  ),
                  hide,
              })
            : [],
    );

    // Nothing to show only when the slot is empty or the task hides every section, not while its image loads.
    const noLayers = $derived(
        target
            ? sections.length === 0
            : workspace.loaded && !workspace.slots[workspace.selected]?.imageId,
    );

    // Kept here, not per viewport, so a section stays open when the selection moves.
    let open: Record<LayerSectionId, boolean> = $state({
        segmentations: true,
        etdrs: false,
        pointsets: false,
        distance: false,
    });
</script>

<p class="px-4 pb-2 text-helper-text-01 text-text-secondary">{subtitle}</p>
{#if noLayers}
    <p class="px-4 text-body-compact-01 text-text-secondary">No layers</p>
{:else if target && sections.length > 0}
    {#key target}
        <LayersContexts
            {target}
            {sections}
            {shown}
            {open}
            ontoggle={(id) => (open = { ...open, [id]: !open[id] })}
        />
    {/key}
{/if}
