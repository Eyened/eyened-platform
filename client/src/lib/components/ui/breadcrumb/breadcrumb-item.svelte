<script lang="ts">
    import type { HTMLLiAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLLiAttributes> = $props();
</script>

<li
    bind:this={ref}
    data-slot="breadcrumb-item"
    class={cn("relative me-2 flex items-center last:me-0", className)}
    {...restProps}
>
    {@render children?.()}
    <span aria-hidden="true" class="ms-2 text-text-primary">/</span>
</li>
