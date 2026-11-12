<!--
@component
A Layers section (level 3) or a group inside one (level 4): a disclosure button with a count, an optional action on the trailing edge, and the body while open.
A closed body is not rendered, so its controls leave the Tab order.
-->
<script lang="ts">
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import type { Snippet } from "svelte";

    let {
        title,
        count,
        open,
        ontoggle,
        level = 3,
        action,
        children,
    }: {
        title: string;
        count: number;
        open: boolean;
        ontoggle: () => void;
        level?: 3 | 4;
        action?: Snippet;
        children: Snippet;
    } = $props();

    const uid = $props.id();
</script>

<div class="flex items-center pe-2">
    <svelte:element this={`h${level}`} class="min-w-0 flex-1">
        <button
            type="button"
            class="flex min-h-8 w-full items-center gap-2 text-start text-text-primary hover:bg-layer-hover-01 {level ===
            3
                ? 'ps-4 text-heading-compact-01'
                : 'ps-8 text-body-compact-01'}"
            aria-expanded={open}
            aria-controls={open ? `${uid}-body` : undefined}
            onclick={ontoggle}
        >
            <ChevronRight
                class="shrink-0 transition-transform {open ? 'rotate-90' : ''}"
                aria-hidden="true"
            />
            <span class="min-w-0 flex-1">{title}</span>
            <span class="pe-2 text-text-secondary">{count}</span>
        </button>
    </svelte:element>
    {@render action?.()}
</div>
{#if open}
    <div id="{uid}-body">{@render children()}</div>
{/if}
