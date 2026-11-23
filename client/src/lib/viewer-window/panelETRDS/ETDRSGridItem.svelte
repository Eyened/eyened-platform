<!--
@component
One ETDRS grid on this image in Layers: eye, the creator's name (sets or unsets the current grid), "This task" and Delete on your own grids.
The current grid shows its fovea and disc edge: on your own grid as today's f / d buttons, which arm the next click, else as text.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { isThisTask } from "$lib/layers/gridLayers.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Position2D } from "$lib/types";
    import { mergeProps } from "bits-ui";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    let {
        formAnnotation,
        shown,
        current,
        armedSlot,
        ontoggleshown,
        ontogglecurrent,
        onarm,
        ondelete,
    }: {
        formAnnotation: FormAnnotationGET;
        shown: boolean;
        current: boolean;
        /** While this is your current grid: the slot the next click places, 0 fovea, 1 disc edge. */
        armedSlot?: number;
        ontoggleshown: () => void;
        ontogglecurrent: () => void;
        onarm: (slot: number) => void;
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
            { label: "Fovea", key: "f", point: data.fovea },
            { label: "Disc edge", key: "d", point: data.disc_edge },
        ];
    });

    function coords(p: Position2D | undefined) {
        return p ? `${Math.round(p.x)}, ${Math.round(p.y)}` : "—";
    }
</script>

<div
    class="border-s-3 {current
        ? 'border-border-interactive bg-layer-selected-01'
        : shown
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
        <Tooltip.Provider delayDuration={100}>
            <Tooltip.Root>
                <Tooltip.Trigger>
                    {#snippet child({ props })}
                        <button
                            {...mergeProps(props, { onclick: ontogglecurrent })}
                            type="button"
                            class="min-h-6 min-w-0 flex-1 px-1 text-start text-body-compact-01 [overflow-wrap:anywhere] text-text-primary hover:bg-layer-hover-01 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                            aria-label="ETDRS grid, {creator}"
                            aria-pressed={current}>{creator}</button
                        >
                    {/snippet}
                </Tooltip.Trigger>
                <Tooltip.Content
                    >ETDRS grid [{formAnnotation.id}]</Tooltip.Content
                >
            </Tooltip.Root>
        </Tooltip.Provider>
        {#if thisTask}<Tag>This task</Tag>{/if}
        {#if canEdit}
            <IconButton size="icon-xs" label="Delete" onclick={ondelete}>
                <TrashCan />
            </IconButton>
        {/if}
    </div>
    {#if current}
        <!-- Starts under the eye, as a segmentation row's details do. -->
        <div class="flex flex-col items-start gap-1 ps-7 pe-2 pb-1">
            {#each landmarks as landmark, slot (landmark.key)}
                {#if armedSlot !== undefined}
                    <Button
                        variant="ghost"
                        size="sm"
                        class="tabular-nums aria-pressed:bg-background-selected aria-pressed:text-text-primary aria-pressed:shadow-content-switcher-selected"
                        aria-pressed={armedSlot === slot}
                        data-landmark={slot}
                        onclick={() => onarm(slot)}
                        >{landmark.label} ({landmark.key}) {coords(
                            landmark.point,
                        )}</Button
                    >
                {:else}
                    <p
                        class="px-1 text-body-compact-01 text-text-primary tabular-nums"
                    >
                        {landmark.label}
                        {coords(landmark.point)}
                    </p>
                {/if}
            {/each}
        </div>
    {/if}
</div>
