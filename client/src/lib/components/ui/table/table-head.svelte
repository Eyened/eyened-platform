<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLThAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLThAttributes> = $props();
</script>

<th
    bind:this={ref}
    data-slot="table-head"
    class={cn(
        "bg-layer-accent-01 px-4 align-middle text-heading-compact-01 whitespace-nowrap text-text-primary table-xl:py-4 table-xl:align-top",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</th>
