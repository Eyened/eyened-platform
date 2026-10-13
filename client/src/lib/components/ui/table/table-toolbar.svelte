<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon data table toolbar: 48 px on layer-01; values from @carbon/styles 1.117.0 data-table/action.
    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLDivElement>> = $props();
</script>

<div
    bind:this={ref}
    data-slot="table-toolbar"
    class={cn("relative flex h-12 w-full items-center bg-layer-01", className)}
    {...restProps}
>
    {@render children?.()}
</div>
