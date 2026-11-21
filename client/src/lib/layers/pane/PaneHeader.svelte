<!--
@component
The Selected pane's fixed header: the full name, the type and save status, then icon actions with Delete set apart at the right.
-->
<script lang="ts">
    import type { Snippet } from "svelte";

    let {
        id,
        name,
        type,
        status,
        actions,
        remove,
    }: {
        /** The heading's id; the pane region is labelled by it. */
        id: string;
        name: string;
        type: string;
        status?: Snippet;
        actions?: Snippet;
        remove?: Snippet;
    } = $props();
</script>

<div class="flex-none border-b border-border-subtle-01 px-4 pt-2 pb-1">
    <h3 {id} class="text-heading-compact-01 wrap-anywhere text-text-primary">
        {name}
    </h3>
    <p
        class="flex flex-wrap items-center gap-x-2 text-helper-text-01 text-text-secondary"
    >
        <span>{type}</span>{@render status?.()}
    </p>
    {#if actions || remove}
        <div class="-ms-2 flex items-center" role="group" aria-label="Actions">
            {@render actions?.()}
            <div class="ms-auto">{@render remove?.()}</div>
        </div>
    {/if}
</div>
