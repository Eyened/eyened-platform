<!--
@component
A ⋯ disclosure: the button shows or hides a short list of buttons, in Tab order. Esc or an item closes it and returns focus to the button.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import OverflowMenuHorizontal from "carbon-icons-svelte/lib/OverflowMenuHorizontal.svelte";
    import type { Snippet } from "svelte";

    let {
        label,
        size = "icon",
        tabindex,
        children,
    }: {
        label: string;
        size?: "icon" | "icon-xs";
        tabindex?: number;
        children: Snippet<[close: () => void]>;
    } = $props();

    // ASSUMPTION: a disclosure, not Carbon's overflow menu, since it holds one item (plan decision 11).
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
<span bind:this={root} class="relative inline-flex" {onfocusout} {onkeydown}>
    <IconButton
        {label}
        {size}
        {tabindex}
        aria-expanded={open}
        aria-controls="{uid}-menu"
        onclick={() => (open = !open)}
    >
        <OverflowMenuHorizontal />
    </IconButton>
    <div
        id="{uid}-menu"
        class="absolute end-0 top-full z-50 flex min-w-max flex-col bg-layer-01 shadow-popover"
        hidden={!open}
    >
        {@render children(close)}
    </div>
</span>
