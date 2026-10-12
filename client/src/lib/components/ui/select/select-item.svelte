<script lang="ts">
    import { Select as SelectPrimitive } from "bits-ui";
    import Checkmark from "carbon-icons-svelte/lib/Checkmark.svelte";
    import { cn, type WithoutChild } from "$lib/utils.js";

    // Carbon Dropdown item (list-box__menu-item), 48 px: hover layer-hover-01, keyboard highlight a
    // focus outline, selected layer-selected-01 with a checkmark; a divider between items.
    let {
        ref = $bindable(null),
        class: className,
        value,
        label,
        children: childrenProp,
        ...restProps
    }: WithoutChild<SelectPrimitive.ItemProps> = $props();
</script>

<SelectPrimitive.Item
    bind:ref
    {value}
    {label}
    data-slot="select-item"
    class={cn(
        "group/item relative h-12 cursor-pointer text-body-compact-01 text-text-secondary select-none hover:bg-layer-hover-01 hover:text-text-primary data-disabled:cursor-not-allowed data-disabled:text-text-disabled data-highlighted:text-text-primary data-highlighted:outline-2 data-highlighted:-outline-offset-2 data-highlighted:outline-focus data-selected:bg-layer-selected-01 data-selected:text-text-primary data-selected:hover:bg-layer-selected-hover-01",
        className,
    )}
    {...restProps}
>
    {#snippet children({ selected, highlighted })}
        <span
            class="mx-4 flex h-full items-center border-t border-border-subtle-01 pe-6 group-first/item:border-transparent group-hover/item:border-transparent group-data-highlighted/item:border-transparent group-data-selected/item:border-transparent after-active-item:border-transparent dropdown-inline:mx-2"
        >
            <span class="truncate">
                {#if childrenProp}
                    {@render childrenProp({ selected, highlighted })}
                {:else}
                    {label || value}
                {/if}
            </span>
        </span>
        {#if selected}
            <Checkmark
                aria-hidden="true"
                class="absolute top-1/2 right-4 -translate-y-1/2 text-icon-primary dropdown-inline:right-2"
            />
        {/if}
    {/snippet}
</SelectPrimitive.Item>
