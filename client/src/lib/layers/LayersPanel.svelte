<!--
@component
The Layers panel body: Layers and Display tabs, the selected viewport's name, then the sections of the shown tab that apply to its image.
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
    import * as Tabs from "$lib/components/ui/tabs/index.js";
    import { layerSections, tabOf, type LayerSectionId } from "./layerSections";

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
                  projection: target.projectionSources.length > 0,
                  localizer: target.localizer.locators().length > 0,
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

    type Tab = "layers" | "display";
    let tab: Tab = $state("layers");
    const bySection = $derived({
        layers: sections.filter((id) => tabOf(id) === "layers"),
        display: sections.filter((id) => tabOf(id) === "display"),
    });
    // A task or an image with no view settings leaves only the Layers tab.
    const current = $derived<Tab>(
        bySection.display.length > 0 ? tab : "layers",
    );

    // Kept on the workspace, not per viewport, so a section stays open when the selection moves.
    function toggle(id: LayerSectionId) {
        workspace.setLayerSection(id, !workspace.layerSections[id]);
    }
</script>

{#snippet body(id: Tab)}
    {#if target && bySection[id].length > 0}
        {#key target}
            <LayersContexts
                {target}
                sections={bySection[id]}
                {shown}
                open={workspace.layerSections}
                ontoggle={toggle}
            />
        {/key}
    {/if}
{/snippet}

<Tabs.Root bind:value={() => current, (v) => (tab = v as Tab)}>
    <Tabs.List aria-label="Layers panel" class="px-4">
        <Tabs.Trigger value="layers">Layers</Tabs.Trigger>
        {#if bySection.display.length > 0}
            <Tabs.Trigger value="display">Display</Tabs.Trigger>
        {/if}
    </Tabs.List>
    <p class="px-4 pt-2 pb-2 text-helper-text-01 text-text-secondary">
        {subtitle}
    </p>
    {#if noLayers}
        <p class="px-4 text-body-compact-01 text-text-secondary">No layers</p>
    {/if}
    <!-- The {#if} unmounts the hidden tab's sections, so the pipette follows the shown tab. -->
    <Tabs.Content value="layers">
        {#if current === "layers"}{@render body("layers")}{/if}
    </Tabs.Content>
    <Tabs.Content value="display">
        {#if current === "display"}{@render body("display")}{/if}
    </Tabs.Content>
</Tabs.Root>
