<script lang="ts">
    import { Accordion as AccordionPrimitive } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import type { Snippet } from "svelte";

    let {
        level = 3,
        summary,
        children,
    }: {
        /** The heading level, one below the heading the accordion sits under. */
        level?: 2 | 3 | 4 | 5 | 6;
        /** What the folded section holds, at the trigger's end in text-secondary; part of its name. */
        summary?: string;
        children: Snippet;
    } = $props();
</script>

<AccordionPrimitive.Header {level}>
    <AccordionPrimitive.Trigger
        class="group flex min-h-10 w-full cursor-pointer items-center pe-4 text-start text-text-primary hover:bg-layer-hover-01 in-dialog:hover:bg-layer-hover-02 in-layer-02:hover:bg-layer-hover-02 in-study:hover:bg-layer-hover-02 in-dialog:in-study:hover:bg-layer-hover-03"
    >
        <!-- The space keeps the summary a separate word in the accessible name; flex does not draw it. The title keeps its width and a long summary ends in an ellipsis. -->
        <span class="flex w-full gap-2 ps-4 text-body-01"
            ><span class="shrink-0">{@render children()}</span>
            {#if summary}<span
                    class="ms-auto min-w-0 truncate pe-2 text-text-secondary"
                    >{summary}</span
                >{/if}</span
        >
        <ChevronDown
            aria-hidden="true"
            class="shrink-0 text-icon-primary transition-transform duration-110 group-data-[state=open]:rotate-180"
        />
    </AccordionPrimitive.Trigger>
</AccordionPrimitive.Header>
