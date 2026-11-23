<!--
@component
One ETDRS grid on this image in Layers: the creator's name (sets or unsets the current grid) and "This task"; eye and Delete on your own grids at the right.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { formAnnotationSavers } from "$lib/saving/formAnnotationSavers";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import { isThisTask } from "$lib/layers/gridLayers.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    let {
        formAnnotation,
        shown,
        current,
        scale,
        ontoggleshown,
        ontogglecurrent,
        ondelete,
    }: {
        formAnnotation: FormAnnotationGET;
        shown: boolean;
        current: boolean;
        /** This grid gives the image's scale. */
        scale: boolean;
        ontoggleshown: () => void;
        ontogglecurrent: () => void;
        ondelete: (event: MouseEvent) => void;
    } = $props();

    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const globalContext = getContext<GlobalContext>("globalContext");
    const canEdit = $derived(globalContext.canEdit(formAnnotation));

    const creator = $derived(formAnnotation.creator.name);
    const thisTask = $derived(
        isThisTask(formAnnotation, taskContext?.subTask?.id),
    );
    // A failed save marks the row until it saves; Retry sits in the grid's pane.
    const saveFailed = $derived(
        formAnnotationSavers.get(formAnnotation.id)?.state === "error",
    );
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
        {#if scale}<Tag>Scale</Tag>{/if}
        {#if saveFailed}<Tag type="red">Couldn't save</Tag>{/if}
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
</LayerRow>
