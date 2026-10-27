<script lang="ts">
    import { Accordion as AccordionPrimitive } from "bits-ui";
    import type { Snippet } from "svelte";

    // Omit<RootProps, ...> loses bits-ui's single/multiple union, so the props are typed here.
    let {
        value = $bindable([]),
        class: className,
        children,
    }: { value?: string[]; class?: string; children?: Snippet } = $props();
</script>

<AccordionPrimitive.Root
    type="multiple"
    bind:value
    data-slot="accordion"
    class={className}
>
    {@render children?.()}
</AccordionPrimitive.Root>
