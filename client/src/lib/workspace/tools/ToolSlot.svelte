<!--
@component
A short-rail job slot: the button arms the tool it shows; the chevron, or a long press on the button, opens the job's list. Esc or a pick closes the list and returns focus to the chevron.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { getContext, type Snippet } from "svelte";
    import type { Workspace } from "../workspace.svelte";
    import type { ToolDef, ToolGroup } from "./registry";

    // ASSUMPTION: TradingView's hold time is not published; 500 ms is a common long-press threshold.
    const LONG_PRESS_MS = 500;

    let {
        group,
        tool,
        tabindex,
        listTabindex,
        children,
    }: {
        group: ToolGroup;
        /** The tool the slot shows: the armed one, else the job's last pick. */
        tool: ToolDef;
        tabindex: number;
        listTabindex: number;
        /** The list rows; `close` hides the list and returns focus to the chevron. */
        children: Snippet<[close: () => void]>;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    let open = $state(false);
    let root: HTMLElement | undefined = $state();
    let chevron: HTMLButtonElement | undefined = $state();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let held = false;

    function close() {
        open = false;
        chevron?.focus();
    }

    function onpointerdown(e: PointerEvent) {
        if (e.button !== 0) return;
        held = false;
        timer = setTimeout(() => {
            held = true;
            open = true;
        }, LONG_PRESS_MS);
    }

    function cancelHold() {
        clearTimeout(timer);
    }

    function onclick() {
        // The click that ends a long press only leaves the list open.
        if (held) {
            held = false;
            return;
        }
        workspace.toggleTool(tool.id);
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
<span bind:this={root} class="relative flex" {onfocusout} {onkeydown}>
    <IconButton
        label={tool.name}
        shortcut={tool.key ?? undefined}
        aria-keyshortcuts={tool.key ?? undefined}
        aria-pressed={workspace.armedTool === tool.id}
        class="aria-pressed:bg-background-selected"
        data-stop={group}
        {tabindex}
        {onpointerdown}
        onpointerup={cancelHold}
        onpointerleave={cancelHold}
        onpointercancel={cancelHold}
        {onclick}
    >
        <tool.icon />
    </IconButton>
    <button
        bind:this={chevron}
        type="button"
        class="flex h-10 w-2 cursor-pointer items-center justify-center text-icon-secondary hover:bg-background-hover hover:text-icon-primary focus-visible:outline-1 focus-visible:-outline-offset-1 focus-visible:outline-focus aria-expanded:bg-background-hover aria-expanded:text-icon-primary"
        aria-label="{group} tools"
        aria-expanded={open}
        aria-controls="{uid}-list"
        data-stop="{group}-list"
        tabindex={listTabindex}
        onclick={() => (open = !open)}
    >
        <!-- A glyph narrower than Carbon's 16 px icons, to fit the 8 px chevron. -->
        <svg width="6" height="10" viewBox="0 0 6 10" aria-hidden="true"
            ><path
                d="M1 1l4 4-4 4"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
            /></svg
        >
    </button>
    <div
        id="{uid}-list"
        data-slot="overflow-menu"
        class="absolute start-full top-0 z-50 flex min-w-max flex-col bg-layer-01 shadow-popover"
        hidden={!open}
    >
        {@render children(close)}
    </div>
</span>
