<script lang="ts">
    import type { HTMLTableAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    // Carbon data table; values from @carbon/styles 1.117.0 data-table. size sets every row's height.
    let {
        ref = $bindable(null),
        class: className,
        size = "md",
        children,
        ...restProps
    }: WithElementRef<HTMLTableAttributes> & { size?: "md" | "xl" } = $props();
</script>

<div data-slot="table-container" class="relative w-full overflow-x-auto">
    <table
        bind:this={ref}
        data-slot="table"
        data-size={size}
        class={cn("w-full border-collapse text-left", className)}
        {...restProps}
    >
        {@render children?.()}
    </table>
</div>
