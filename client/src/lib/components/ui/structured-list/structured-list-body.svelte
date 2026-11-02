<script lang="ts">
    import type { HTMLAttributes } from "svelte/elements";

    let { children, ...restProps }: HTMLAttributes<HTMLTableSectionElement> =
        $props();
</script>

<tbody {...restProps}>{@render children?.()}</tbody>
