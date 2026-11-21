<!--
@component
One ETDRS grid on this image in Layers: the creator's name (sets or unsets the current grid) and "This task"; eye and Delete on your own grids at the right.
The current grid shows its fovea and disc edge as text; Place ETDRS (G) places them.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import { isThisTask } from "$lib/layers/gridLayers.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Position2D } from "$lib/types";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    let {
        formAnnotation,
        shown,
        current,
        ontoggleshown,
        ontogglecurrent,
        ondelete,
    }: {
        formAnnotation: FormAnnotationGET;
        shown: boolean;
        current: boolean;
        ontoggleshown: () => void;
        ontogglecurrent: () => void;
        ondelete: () => void;
    } = $props();

    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const globalContext = getContext<GlobalContext>("globalContext");
    const canEdit = $derived(globalContext.canEdit(formAnnotation));

    const creator = $derived(formAnnotation.creator.name);
    const thisTask = $derived(
        isThisTask(formAnnotation, taskContext?.subTask?.id),
    );
    const landmarks = $derived.by(() => {
        const data = (formAnnotation.form_data ?? {}) as Record<
            string,
            Position2D | undefined
        >;
        return [
            { label: "Fovea", point: data.fovea },
            { label: "Disc edge", point: data.disc_edge },
        ];
    });

    function coords(p: Position2D | undefined) {
        return p ? `${Math.round(p.x)}, ${Math.round(p.y)}` : "—";
    }
</script>

<LayerRow
    label="ETDRS grid, {creator} [{formAnnotation.id}]"
    name={creator}
    nameLabel="ETDRS grid, {creator}"
    tooltip="ETDRS grid, {creator} [{formAnnotation.id}]"
    selected={current}
    visible={shown}
    onselect={ontogglecurrent}
>
    {#snippet tags()}
        {#if thisTask}<Tag>This task</Tag>{/if}
    {/snippet}
    {#snippet icons()}
        <IconButton
            size="icon-xs"
            label={shown ? "Hide" : "Show"}
            data-sticky={!shown}
            onclick={ontoggleshown}
        >
            {#if shown}<View />{:else}<ViewOff />{/if}
        </IconButton>
        {#if canEdit}
            <IconButton size="icon-xs" label="Delete" onclick={ondelete}>
                <TrashCan />
            </IconButton>
        {/if}
    {/snippet}
    {#if current}
        <!-- Starts under the name, as a segmentation row's details do. -->
        <div class="flex flex-col items-start gap-1 ps-7 pe-2 pb-1">
            {#each landmarks as landmark (landmark.label)}
                <p
                    class="px-1 text-body-compact-01 text-text-primary tabular-nums"
                >
                    {landmark.label}
                    {coords(landmark.point)}
                </p>
            {/each}
        </div>
    {/if}
</LayerRow>
