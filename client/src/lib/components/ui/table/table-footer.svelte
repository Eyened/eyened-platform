<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLTableSectionElement>> = $props();
</script>

<tfoot
    bind:this={ref}
    data-slot="table-footer"
    class={cn(
        "border-t border-border-subtle-01 bg-layer-accent-01 text-heading-compact-01",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</tfoot>
