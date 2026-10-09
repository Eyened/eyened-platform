<script lang="ts">
    import type { HTMLAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLDivElement>> = $props();
</script>

<div
    bind:this={ref}
    data-slot="card"
    class={cn(
        "rounded-xl bg-card text-card-foreground shadow-sm flex flex-col gap-6 border py-6",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</div>
