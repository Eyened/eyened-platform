<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLTableAttributes } from "svelte/elements";

    // Carbon StructuredList (@carbon/styles 1.117.0 structured-list); `condensed` is Carbon React's isCondensed.
    let {
        condensed = false,
        class: className,
        children,
        ...restProps
    }: HTMLTableAttributes & { condensed?: boolean } = $props();
</script>

<table
    data-slot="structured-list"
    data-condensed={condensed || undefined}
    class={cn("w-full border-collapse", className)}
    {...restProps}
>
    {@render children?.()}
</table>
