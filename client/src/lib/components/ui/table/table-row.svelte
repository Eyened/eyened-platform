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
        // Carbon data table colours are contextual: inside a dialog (layer-01) the table sits one layer up.
        "group h-10 border-b border-border-subtle-01 bg-layer-01 hover:bg-layer-hover-01 in-dialog:border-border-subtle-02 in-dialog:bg-layer-02 in-dialog:hover:bg-layer-hover-02 table-xl:h-16 table-lg:h-12",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</tr>
