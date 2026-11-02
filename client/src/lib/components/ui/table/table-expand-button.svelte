<script lang="ts">
    import { cn } from "$lib/utils.js";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import type { HTMLButtonAttributes } from "svelte/elements";

    // Carbon data table expand toggle (Carbon React TableExpandRow / TableExpandHeader); values from
    // @carbon/styles 1.117.0 data-table/expandable. The caller sets aria-label and aria-controls.
    let {
        expanded,
        ontoggle,
        ...restProps
    }: Omit<HTMLButtonAttributes, "onclick" | "aria-expanded"> & {
        expanded: boolean;
        ontoggle: () => void;
    } = $props();
</script>

<button
    type="button"
    aria-expanded={expanded}
    onclick={ontoggle}
    class="flex h-12 w-full cursor-pointer items-center justify-center px-2"
    {...restProps}
>
    <ChevronRight
        aria-hidden="true"
        class={cn(
            "text-layer-selected-inverse transition-transform duration-110",
            expanded ? "rotate-270" : "rotate-90",
        )}
    />
</button>
