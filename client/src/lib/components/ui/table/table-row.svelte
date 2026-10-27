<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLTableRowElement>> = $props();
</script>

<tr
    bind:this={ref}
    data-slot="table-row"
    class={cn(
        "group h-10 border-b border-border-subtle-01 bg-layer-01 hover:bg-layer-hover-01 table-xl:h-16",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</tr>
