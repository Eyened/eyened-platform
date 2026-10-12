<script lang="ts">
    import type { HTMLOlAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLOlAttributes> = $props();
</script>

<ol
    bind:this={ref}
    data-slot="breadcrumb-list"
    class={cn("flex flex-wrap text-body-compact-01", className)}
    {...restProps}
>
    {@render children?.()}
</ol>
