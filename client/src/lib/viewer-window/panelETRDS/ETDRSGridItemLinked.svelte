<!--
@component
A grid on a registered image, read-only in Layers: the creator's name with the image and grid IDs under it, "This task", and the eye.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import { isThisTask } from "$lib/layers/gridLayers.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    let {
        formAnnotation,
        shown,
        ontoggleshown,
    }: {
        formAnnotation: FormAnnotationGET;
        shown: boolean;
        ontoggleshown: () => void;
    } = $props();

    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const creator = $derived(formAnnotation.creator.name);
</script>

<LayerRow
    label="ETDRS grid, {creator} [{formAnnotation.id}]"
    name={creator}
    tooltip="ETDRS grid, {creator} [{formAnnotation.id}]"
    visible={shown}
>
    {#snippet tags()}
        {#if isThisTask(formAnnotation, taskContext?.subTask?.id)}
            <Tag>This task</Tag>
        {/if}
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
    {/snippet}
    <p
        class="ps-(--row-indent) pe-2 pb-1 text-helper-text-01 text-text-secondary"
    >
        [{formAnnotation.image_id}] [{formAnnotation.id}]
    </p>
</LayerRow>
