<!--
@component
Layers › ETDRS grids for the selected viewport: the AI grid, this image's grids, then grids linked from registered images.
The section places nothing: a row sets the current grid; New also arms Place ETDRS (G) at Fovea.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import { createFormAnnotation, formSchemasByName } from "$lib/data";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import ETDRSGridItem from "$lib/viewer-window/panelETRDS/ETDRSGridItem.svelte";
    import ETDRSGridItemLinked from "$lib/viewer-window/panelETRDS/ETDRSGridItemLinked.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext, tick } from "svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import { AI_GRID, aiGrid, type GridLayers } from "./gridLayers.svelte";
    import GridDeleteModal from "./GridDeleteModal.svelte";
    import LayerRow from "./LayerRow.svelte";
    import LayerSection from "./LayerSection.svelte";

    let {
        grids,
        open,
        ontoggle,
    }: {
        grids: GridLayers;
        open: boolean;
        ontoggle: () => void;
    } = $props();

    const uid = $props.id();
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const workspace = getContext<Workspace>("workspace");
    const { instance } = viewerContext.image;
    let section: HTMLElement | undefined = $state();

    let deleting: FormAnnotationGET | null = $state(null);
    let deleteOpen = $state(false);
    function askDelete(grid: FormAnnotationGET) {
        deleting = grid;
        deleteOpen = true;
    }

    const all = $derived(grids.list());
    const own = $derived(all.filter((g) => g.image_id == instance.id));
    const linked = $derived(all.filter((g) => g.image_id != instance.id));
    const ai = $derived(aiGrid(viewerContext.image));
    const aiShown = $derived(grids.isShown(AI_GRID));
    const count = $derived(own.length + linked.length + (ai ? 1 : 0));

    async function create() {
        const schemaId = formSchemasByName.get(
            BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID,
        )?.id;
        if (schemaId === undefined) return;
        if (!open) ontoggle();
        grids.hideAll();
        const grid = await createFormAnnotation({
            form_schema_id: schemaId,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_id: instance.id,
            laterality: instance.laterality ?? undefined,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
        grids.setCurrent(grid.id);
        // New shows the grid it makes; selecting a grid otherwise leaves it hidden or shown.
        grids.setShown(grid.id, true);
        // The next step is placing the fovea.
        workspace.etdrsSlot = 0;
        workspace.arm("etdrs");
        // The pressed button may be gone (the empty state), so focus goes to the new grid's row.
        await tick();
        section
            ?.querySelector<HTMLElement>(
                `[aria-label$="[${grid.id}]"] button[aria-pressed]`,
            )
            ?.focus();
    }
</script>

<div bind:this={section}>
    <LayerSection title="ETDRS grids" {count} {open} {ontoggle}>
        {#snippet action()}
            <Button
                variant="ghost"
                size="sm"
                aria-label="New ETDRS grid"
                onclick={create}>New</Button
            >
        {/snippet}
        {#if count > 0}
            <ul>
                {#if ai}
                    <li>
                        <LayerRow
                            label="AI grid"
                            name="AI grid"
                            visible={aiShown}
                        >
                            {#snippet tags()}<Tag>AI</Tag>{/snippet}
                            {#snippet icons()}
                                <IconButton
                                    size="icon-xs"
                                    label={aiShown ? "Hide" : "Show"}
                                    data-sticky={!aiShown}
                                    onclick={() =>
                                        grids.setShown(AI_GRID, !aiShown)}
                                >
                                    {#if aiShown}<View />{:else}<ViewOff />{/if}
                                </IconButton>
                            {/snippet}
                        </LayerRow>
                    </li>
                {/if}
                {#each own as grid (grid.id)}
                    <li>
                        <ETDRSGridItem
                            formAnnotation={grid}
                            shown={grids.isShown(grid.id)}
                            current={grids.currentId === grid.id}
                            ontoggleshown={() =>
                                grids.setShown(
                                    grid.id,
                                    !grids.isShown(grid.id),
                                )}
                            ontogglecurrent={() =>
                                grids.setCurrent(
                                    grids.currentId === grid.id
                                        ? undefined
                                        : grid.id,
                                )}
                            ondelete={() => askDelete(grid)}
                        />
                    </li>
                {/each}
            </ul>
            {#if linked.length > 0}
                <p
                    id="{uid}-linked"
                    class="px-4 pt-2 pb-1 text-label-01 text-text-secondary"
                >
                    Linked from registered images
                </p>
                <ul aria-labelledby="{uid}-linked">
                    {#each linked as grid (grid.id)}
                        <li>
                            <ETDRSGridItemLinked
                                formAnnotation={grid}
                                shown={grids.isShown(grid.id)}
                                ontoggleshown={() =>
                                    grids.setShown(
                                        grid.id,
                                        !grids.isShown(grid.id),
                                    )}
                            />
                        </li>
                    {/each}
                </ul>
            {/if}
        {:else}
            <Empty.Root class="px-4 py-6">
                <Empty.Header>
                    <!-- ASSUMPTION: the spec asks for a title and a description but gives no text. -->
                    <Empty.Title>No ETDRS grids</Empty.Title>
                    <Empty.Description
                        >Create one to place the fovea and disc edge.</Empty.Description
                    >
                </Empty.Header>
                <Button variant="ghost" size="sm" onclick={create}
                    >New ETDRS grid <Add /></Button
                >
            </Empty.Root>
        {/if}
    </LayerSection>
</div>
<GridDeleteModal
    grid={deleting}
    {grids}
    bind:open={deleteOpen}
    onfallback={() => section?.querySelector<HTMLElement>("button")?.focus()}
/>
