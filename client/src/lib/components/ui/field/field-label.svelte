<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import type { ComponentProps } from "svelte";

    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: ComponentProps<typeof Label> = $props();
</script>

<Label bind:ref data-slot="field-label" class={className} {...restProps}>
    {@render children?.()}
</Label>
