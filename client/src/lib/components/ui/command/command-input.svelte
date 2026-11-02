<script lang="ts">
    import { Command as CommandPrimitive } from "bits-ui";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Search from "carbon-icons-svelte/lib/Search.svelte";
    import { cn } from "$lib/utils.js";

    // Carbon Search, size sm (32 px), on a layer (field-02); values from @carbon/styles 1.117.0
    // search/_search.scss. Escape clears a non-empty field before a popover sees it.
    let {
        ref = $bindable(null),
        class: className,
        value = $bindable(""),
        ...restProps
    }: CommandPrimitive.InputProps = $props();
</script>

<div class="relative flex h-8 items-center" data-slot="command-input-wrapper">
    <Search
        aria-hidden="true"
        class="pointer-events-none absolute start-2 text-icon-secondary"
    />
    <CommandPrimitive.Input
        data-slot="command-input"
        class={cn(
            "h-8 w-full border-0 border-b border-border-strong-02 bg-field-02 px-8 text-body-compact-01 text-text-primary placeholder:text-text-placeholder",
            className,
        )}
        bind:ref
        {...restProps}
        bind:value
        onkeydown={(e) => {
            if (e.key === "Escape" && value) {
                e.stopPropagation();
                value = "";
            }
        }}
    />
    {#if value}
        <button
            type="button"
            aria-label="Clear search input"
            class="absolute end-0 flex size-8 cursor-pointer items-center justify-center text-icon-primary hover:bg-field-hover-02"
            onclick={() => {
                value = "";
                ref?.focus();
            }}
        >
            <Close />
        </button>
    {/if}
</div>
