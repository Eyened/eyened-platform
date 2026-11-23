<!--
@component
A Layers section (level 3) or a group inside one (level 4): a 24 px disclosure button with a count or a short text (left out for settings sections), an optional action on the trailing edge, and the body while open.
A layer type or group (one with a count) draws a guide line down its open body under its chevron. With a count of 0 it shows `empty` as one hint line there. A closed body is not rendered, so its controls leave the Tab order.
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
        empty,
        action,
        children,
    }: {
        title: string;
        count?: number | string;
        open: boolean;
        ontoggle: () => void;
        level?: 3 | 4;
        /** One hint line under an open type with no rows. */
        empty?: string;
        action?: Snippet;
        children: Snippet;
    } = $props();

    const uid = $props.id();
</script>

<div class="flex items-center pe-2 hover:bg-layer-hover-01">
    <svelte:element this={`h${level}`} class="min-w-0 flex-1">
        <button
            type="button"
            class="flex min-h-6 w-full items-center gap-2 text-start text-text-primary {level ===
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
            <span class="min-w-0 flex-1 truncate">{title}</span>
            {#if count !== undefined}
                <span class="pe-2 text-text-secondary">{count}</span>
            {/if}
        </button>
    </svelte:element>
    {@render action?.()}
</div>
{#if open}
    <div
        id="{uid}-body"
        class:guide={count !== undefined}
        style:--guide={level === 3 ? "23px" : "39px"}
    >
        {@render children()}
        {#if count === 0 && empty}
            <p
                class="flex min-h-6 items-center ps-8 pe-4 text-label-01 text-text-secondary"
            >
                {empty}
            </p>
        {/if}
    </div>
{/if}

<style>
    /* 1 px under the chevron's centre; positioned, so it shows over the rows' fills. */
    .guide {
        position: relative;
    }
    .guide::before {
        content: "";
        position: absolute;
        inset-block: 0;
        inset-inline-start: var(--guide);
        width: 1px;
        background: var(--color-border-subtle-01);
        pointer-events: none;
    }
</style>
