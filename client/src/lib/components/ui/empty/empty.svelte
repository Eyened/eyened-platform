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
        "flex min-w-0 flex-col items-start gap-4 py-12 text-left",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</div>
