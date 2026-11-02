<script lang="ts">
    import { Accordion as AccordionPrimitive } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import type { Snippet } from "svelte";

    let { children }: { children: Snippet } = $props();
</script>

<AccordionPrimitive.Header level={3}>
    <AccordionPrimitive.Trigger
        class="group flex min-h-10 w-full cursor-pointer items-center pe-4 text-start text-text-primary hover:bg-layer-hover-01 in-dialog:hover:bg-layer-hover-02 in-study:hover:bg-layer-hover-02 in-dialog:in-study:hover:bg-layer-hover-03"
    >
        <span class="w-full ps-4 text-body-01">{@render children()}</span>
        <ChevronDown
            aria-hidden="true"
            class="shrink-0 text-icon-primary transition-transform duration-110 group-data-[state=open]:rotate-180"
        />
    </AccordionPrimitive.Trigger>
</AccordionPrimitive.Header>
