<script lang="ts">
    import type { HTMLAttributes } from "svelte/elements";

    let { children, ...restProps }: HTMLAttributes<HTMLTableSectionElement> =
        $props();
</script>

<thead {...restProps}>{@render children?.()}</thead>
