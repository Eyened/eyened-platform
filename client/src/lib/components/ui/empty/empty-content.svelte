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
    class={cn("flex flex-col items-start gap-4", className)}
    {...restProps}
>
    {@render children?.()}
</div>
