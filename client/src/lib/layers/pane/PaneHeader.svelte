<!--
@component
The Selected pane's fixed header, in the selected row's look: an optional colour chip and the full name, the type and save status, then icon actions with Delete set apart at the right.
-->
<script lang="ts">
    import type { Snippet } from "svelte";

    let {
        id,
        name,
        type,
        swatch,
        status,
        actions,
        remove,
    }: {
        /** The heading's id; the pane region is labelled by it. */
        id: string;
        name: string;
        type: string;
        /** A one-class segmentation's colour, drawn as a static chip as on its row. */
        swatch?: string;
        status?: Snippet;
        actions?: Snippet;
        remove?: Snippet;
    } = $props();
</script>

<!-- The selected row's fill and 3 px bar; ps-3.25 keeps the text at 16 px. -->
<div
    class="flex-none border-s-3 border-b border-s-border-interactive border-b-border-subtle-01 bg-layer-selected-01 ps-3.25 pe-4 pt-2 pb-1"
>
    <h3
        {id}
        class="flex items-center gap-2 text-heading-compact-01 wrap-anywhere text-text-primary"
    >
        {#if swatch}
            <span
                class="size-3 shrink-0 rounded-full"
                style:background-color={swatch}
                aria-hidden="true"
            ></span>
        {/if}
        <span class="min-w-0">{name}</span>
    </h3>
    <div
        class="flex flex-wrap items-center gap-x-2 text-helper-text-01 text-text-secondary"
    >
        <span>{type}</span>{@render status?.()}
    </div>
    {#if actions || remove}
        <div class="-ms-2 flex items-center" role="group" aria-label="Actions">
            {@render actions?.()}
            <div class="ms-auto">{@render remove?.()}</div>
        </div>
    {/if}
</div>
