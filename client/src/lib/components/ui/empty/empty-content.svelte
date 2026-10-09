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
    data-slot="empty-content"
    class={cn(
        "max-w-sm text-sm flex w-full min-w-0 flex-col items-center gap-4 text-balance",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</div>
