<!--
@component
A ⋯ disclosure: the button shows or hides a short list of buttons, in Tab order. Esc or an item closes it and returns focus to the button. The palette's ⋯ More tools passes the armed tool's icon when one of its tools is armed.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import OverflowMenuHorizontal from "carbon-icons-svelte/lib/OverflowMenuHorizontal.svelte";
    import type { Snippet } from "svelte";

    let {
        label,
        size = "icon",
        tabindex,
        icon,
        side = "bottom",
        active = false,
        stop,
        children,
    }: {
        label: string;
        size?: "icon" | "icon-xs";
        tabindex?: number;
        /** Replaces the ⋯ icon. */
        icon?: Snippet;
        /** "end" opens the list beside the button, for the palette. */
        side?: "bottom" | "end";
        /** Shows the button selected, as for an armed tool. */
        active?: boolean;
        /** The palette's roving-focus key. */
        stop?: string;
        children: Snippet<[close: () => void]>;
    } = $props();

    // ASSUMPTION: a disclosure, not Carbon's overflow menu, since its list is a few plain buttons.
    const uid = $props.id();
    let open = $state(false);
    let root: HTMLElement | undefined = $state();

    /** Hides the list and returns focus to the ⋯ button. */
    function close() {
        open = false;
        root?.querySelector<HTMLElement>("button")?.focus();
    }

    function onfocusout(e: FocusEvent) {
        const to = e.relatedTarget as Node | null;
        if (to && !root?.contains(to)) open = false;
    }

    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Escape" || !open) return;
        e.stopPropagation();
        close();
    }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
    bind:this={root}
    class="relative inline-flex"
    data-stop={stop}
    {onfocusout}
    {onkeydown}
>
    <IconButton
        {label}
        {size}
        {tabindex}
        class={active ? "bg-background-selected" : undefined}
        aria-expanded={open}
        aria-controls="{uid}-menu"
        onclick={() => (open = !open)}
    >
        {#if icon}{@render icon()}{:else}<OverflowMenuHorizontal />{/if}
    </IconButton>
    <div
        id="{uid}-menu"
        data-slot="overflow-menu"
        class="absolute z-50 flex min-w-max flex-col bg-layer-01 shadow-popover {side ===
        'end'
            ? 'start-full top-0'
            : 'end-0 top-full'}"
        hidden={!open}
    >
        {@render children(close)}
    </div>
</span>
