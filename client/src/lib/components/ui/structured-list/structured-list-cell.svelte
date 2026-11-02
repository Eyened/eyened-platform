<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLTdAttributes } from "svelte/elements";

    let {
        head = false,
        class: className,
        children,
        ...restProps
    }: HTMLTdAttributes & { head?: boolean } = $props();
</script>

{#if head}
    <th
        class={cn(
            "h-10 px-2 pt-4 pb-2 text-start align-top text-heading-compact-01 text-text-primary first:ps-4 list-condensed:p-2 list-condensed:first:ps-4",
            className,
        )}
        {...restProps}
    >
        {@render children?.()}
    </th>
{:else}
    <td
        class={cn(
            "px-2 pt-4 pb-6 align-top text-body-01 text-text-secondary first:ps-4 list-condensed:p-2 list-condensed:first:ps-4",
            className,
        )}
        {...restProps}
    >
        {@render children?.()}
    </td>
{/if}
