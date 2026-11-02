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
    data-slot="empty-description"
    class={cn(
        "text-body-01 text-text-secondary [&>a]:text-link-primary [&>a:hover]:text-link-primary-hover",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</div>
