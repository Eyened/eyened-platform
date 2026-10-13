<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLTdAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLTdAttributes> = $props();
</script>

<td
    bind:this={ref}
    data-slot="table-cell"
    class={cn(
        "px-4 align-middle text-body-compact-01 text-text-secondary group-hover:text-text-primary table-xl:py-4 table-xl:align-top",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</td>
