<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon expanded row (Carbon React TableExpandedRow); values from @carbon/styles 1.117.0
    // data-table/expandable. It hovers with the row above it; that row adds
    // has-[+tr:hover]:bg-layer-hover-01 while expanded.
    let {
        ref = $bindable(null),
        colspan,
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLTableRowElement>> & {
        colspan: number;
    } = $props();
</script>

<tr
    bind:this={ref}
    data-slot="table-expanded-row"
    class={cn(
        "border-b border-border-subtle-01 bg-layer-01 hover:bg-layer-hover-01 [tr:hover+&]:bg-layer-hover-01",
        className,
    )}
    {...restProps}
>
    <td
        {colspan}
        class="ps-14 pe-4 pt-4 pb-6 text-body-compact-01 text-text-primary"
    >
        {@render children?.()}
    </td>
</tr>
