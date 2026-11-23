<!--
@component
A grid on a registered image, read-only in Layers: eye, the creator's name with the image and grid IDs under it, and "This task".
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
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

<div
    class="border-s-3 {shown
        ? 'border-border-strong-01'
        : 'border-transparent'}"
    role="group"
    aria-label="ETDRS grid, {creator} [{formAnnotation.id}]"
>
    <div class="flex items-start gap-1 py-1 ps-7 pe-2">
        <IconButton
            size="icon-xs"
            label={shown ? "Hide" : "Show"}
            onclick={ontoggleshown}
        >
            {#if shown}<View />{:else}<ViewOff />{/if}
        </IconButton>
        <div class="min-w-0 flex-1 px-1">
            <p
                class="text-body-compact-01 [overflow-wrap:anywhere] text-text-primary"
            >
                {creator}
            </p>
            <p class="text-helper-text-01 text-text-secondary">
                [{formAnnotation.image_id}] [{formAnnotation.id}]
            </p>
        </div>
        {#if isThisTask(formAnnotation, taskContext?.subTask?.id)}
            <Tag>This task</Tag>
        {/if}
    </div>
</div>
