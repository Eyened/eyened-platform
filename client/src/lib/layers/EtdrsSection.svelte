<!--
@component
Layers › ETDRS grids for the selected viewport: the AI grid, this image's grids, then grids linked from registered images.
Until the Place ETDRS tool comes, your current grid keeps today's f / d placing.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import {
        createFormAnnotation,
        formAnnotations,
        formSchemasByName,
        setFormAnnotationValue,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { ImagePoint, PointList } from "$lib/forms/pointSchema";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { ETDRS_LANDMARK_COLOUR } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import ETDRSGridItem from "$lib/viewer-window/panelETRDS/ETDRSGridItem.svelte";
    import ETDRSGridItemLinked from "$lib/viewer-window/panelETRDS/ETDRSGridItemLinked.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext, tick, untrack } from "svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import { AI_GRID, aiGrid, type GridLayers } from "./gridLayers.svelte";
    import LayerSection from "./LayerSection.svelte";

    let {
        grids,
        open,
        ontoggle,
        shown,
    }: {
        grids: GridLayers;
        open: boolean;
        ontoggle: () => void;
        /** True while Layers is on screen. */
        shown: boolean;
    } = $props();

    const LANDMARK_SLOTS = ["fovea", "disc_edge"] as const;
    const uid = $props.id();
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { instance } = viewerContext.image;
    let section: HTMLElement | undefined = $state();

    const all = $derived(grids.list());
    const own = $derived(all.filter((g) => g.image_id == instance.id));
    const linked = $derived(all.filter((g) => g.image_id != instance.id));
    const ai = $derived(aiGrid(viewerContext.image));
    const aiShown = $derived(grids.isShown(AI_GRID));
    const count = $derived(own.length + linked.length + (ai ? 1 : 0));

    // Today's f / d placing writes into your current grid on this image, while this section is open and on screen.
    const editableId = $derived.by(() => {
        if (!shown || !open || grids.currentId === undefined) return undefined;
        const grid = formAnnotations.get(grids.currentId);
        return grid &&
            grid.image_id == instance.id &&
            globalContext.canEdit(grid)
            ? grid.id
            : undefined;
    });
    let armed: { id: number; tool: PointTool } | undefined = $state();
    $effect(() => {
        const id = editableId;
        if (id === undefined) return;
        const tool = new PointTool({
            canEdit: true,
            pointStyle: "cross",
            radius: 16,
            color: ETDRS_LANDMARK_COLOUR,
            cardinality: "list",
            sparse: true,
            // Fovea and disc edge are en-face 2D landmarks, without a B-scan index.
            coordinateSpace: "enface2d",
            slotLabels: ["Fovea", "Disc edge"],
            slotKeys: [
                { index: 0, key: "f" },
                { index: 1, key: "d" },
            ],
            onChange: (points) => writeLandmarks(id, points, false),
            onPersist: (points) => writeLandmarks(id, points, true),
        });
        untrack(() => {
            tool.points = pointsOf(formAnnotations.get(id));
            tool.placementIndex = grids.slot;
        });
        const remove = viewerContext.addOverlay(tool);
        armed = { id, tool };
        return () => {
            // Keep the armed slot for when this grid shows again; a newly set grid starts at Fovea.
            if (grids.currentId === id) grids.slot = tool.placementIndex ?? 0;
            armed = undefined;
            tool.destroy();
            remove();
        };
    });

    function armedSlot(grid: FormAnnotationGET): number | undefined {
        if (grid.id !== editableId) return undefined;
        // The tool may still be the previous grid's until the effect swaps it.
        return armed?.id === grid.id
            ? (armed.tool.placementIndex ?? grids.slot)
            : grids.slot;
    }

    function arm(slot: number) {
        grids.slot = slot;
        if (armed) armed.tool.placementIndex = slot;
    }

    function isImagePoint(value: unknown): value is ImagePoint {
        return (
            typeof value === "object" &&
            value !== null &&
            typeof (value as ImagePoint).x === "number" &&
            typeof (value as ImagePoint).y === "number"
        );
    }

    function pointsOf(grid: FormAnnotationGET | undefined): PointList {
        const data = (grid?.form_data ?? {}) as Record<string, unknown>;
        return LANDMARK_SLOTS.map((slot) => {
            const value = data[slot];
            return isImagePoint(value) ? value : null;
        });
    }

    function writeLandmarks(id: number, points: PointList, persist: boolean) {
        const grid = formAnnotations.get(id);
        if (!grid) return;
        const data = { ...(grid.form_data as Record<string, unknown>) };
        LANDMARK_SLOTS.forEach((slot, i) => {
            const point = points[i];
            if (point == null) delete data[slot];
            else data[slot] = point;
        });
        formAnnotations.set(id, { ...grid, form_data: data });
        if (persist) setFormAnnotationValue(id, data);
    }

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
        // The button that was pressed may be gone (the empty state); the next step is placing the fovea.
        await tick();
        section
            ?.querySelector<HTMLElement>(
                `[aria-label="ETDRS grid, ${grid.creator.name} [${grid.id}]"] [data-landmark="0"]`,
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
                        <div
                            class="flex items-start gap-1 border-s-3 py-1 ps-7 pe-2 {aiShown
                                ? 'border-border-strong-01'
                                : 'border-transparent'}"
                            role="group"
                            aria-label="AI grid"
                        >
                            <IconButton
                                size="icon-xs"
                                label={aiShown ? "Hide" : "Show"}
                                onclick={() =>
                                    grids.setShown(AI_GRID, !aiShown)}
                            >
                                {#if aiShown}<View />{:else}<ViewOff />{/if}
                            </IconButton>
                            <span
                                class="min-h-6 flex-1 px-1 text-body-compact-01 text-text-primary"
                                >AI grid</span
                            >
                            <Tag>AI</Tag>
                        </div>
                    </li>
                {/if}
                {#each own as grid (grid.id)}
                    <li>
                        <ETDRSGridItem
                            formAnnotation={grid}
                            shown={grids.isShown(grid.id)}
                            current={grids.currentId === grid.id}
                            armedSlot={armedSlot(grid)}
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
                            onarm={arm}
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
