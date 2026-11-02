<script lang="ts">
    import { cn } from "$lib/utils.js";

    // Carbon ContentSwitcher, low contrast (the default selected option is a light bar on Gray 100).
    // Values from @carbon/styles 1.117.0 content-switcher/_content-switcher.scss; keys from Carbon React
    // ContentSwitcher. Automatic: an arrow key selects. Manual: arrows move focus, Enter or Space selects.
    // Grid of equal columns: with w-fit, every option is as wide as the longest label.
    let {
        items,
        selectedId = $bindable(),
        label,
        size = "md",
        selectionMode = "automatic",
        onchange,
        class: className,
    }: {
        items: { id: string; text: string }[];
        selectedId?: string;
        label: string;
        size?: "md" | "lg";
        selectionMode?: "automatic" | "manual";
        onchange?: (selectedId: string) => void;
        class?: string;
    } = $props();

    const tabs: HTMLButtonElement[] = $state([]);

    function select(id: string) {
        if (id === selectedId) return;
        selectedId = id;
        onchange?.(id);
    }

    function onkeydown(e: KeyboardEvent, index: number) {
        const step =
            e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!step) return;
        e.preventDefault();
        const next = (index + step + items.length) % items.length;
        tabs[next]?.focus();
        if (selectionMode === "automatic") select(items[next].id);
    }
</script>

<div
    role="tablist"
    aria-label={label}
    class={cn(
        "grid w-full auto-cols-fr grid-flow-col overflow-hidden rounded-content-switcher border border-border-strong-01 in-dialog:border-border-strong-02",
        size === "lg" ? "h-12" : "h-10",
        className,
    )}
>
    {#each items as item, i (item.id)}
        {@const selected = item.id === selectedId}
        <button
            bind:this={tabs[i]}
            type="button"
            role="tab"
            aria-selected={selected}
            tabindex={selected ? 0 : -1}
            data-selected={selected || undefined}
            class={cn(
                "relative flex min-w-0 cursor-pointer items-center text-start text-body-compact-01 whitespace-nowrap text-text-secondary hover:bg-content-switcher-background-hover hover:text-text-primary",
                // 1 × 16 px divider between options, hidden next to a hovered, focused or selected one
                "before:absolute before:start-0 before:h-4 before:w-px before:bg-border-strong-01 first:before:hidden hover:before:hidden focus-visible:before:hidden data-selected:before:hidden [&:focus-visible+&]:before:hidden [&:hover+&]:before:hidden [[data-selected]+&]:before:hidden",
                "data-selected:rounded-content-switcher data-selected:bg-content-switcher-selected data-selected:text-heading-compact-01 data-selected:text-text-primary data-selected:shadow-content-switcher-selected data-selected:hover:bg-content-switcher-selected",
                size === "lg" ? "px-3.5" : "px-4",
            )}
            onclick={() => select(item.id)}
            onkeydown={(e) => onkeydown(e, i)}
        >
            <span class="truncate">{item.text}</span>
        </button>
    {/each}
</div>
