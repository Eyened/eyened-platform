<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        class: className,
        children,
        ...restProps
    }: HTMLAttributes<HTMLDivElement> = $props();
</script>

<div
    data-slot="empty"
    class={cn(
        "rounded-lg md:p-12 flex min-w-0 flex-1 flex-col items-center justify-center gap-6 border-dashed p-6 text-center text-balance",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</div>
