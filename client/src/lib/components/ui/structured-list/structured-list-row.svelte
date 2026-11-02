<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        head = false,
        class: className,
        children,
        ...restProps
    }: HTMLAttributes<HTMLTableRowElement> & { head?: boolean } = $props();
</script>

<tr
    class={cn(
        !head &&
            "border-t border-border-subtle-00 last:border-b in-dialog:border-border-subtle-01",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</tr>
