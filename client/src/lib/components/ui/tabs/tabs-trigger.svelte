<script lang="ts">
    import { Tabs as TabsPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    // Carbon line tab, md: 40 px, 2 px bottom border, 1 px between tabs.
    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: TabsPrimitive.TriggerProps = $props();
</script>

<TabsPrimitive.Trigger
    bind:ref
    data-slot="tabs-trigger"
    class={cn(
        "h-10 border-b-2 border-border-subtle-00 px-4 py-2 text-body-compact-01 whitespace-nowrap text-text-secondary not-first:ms-px hover:border-border-strong-01 hover:text-text-primary disabled:border-border-disabled disabled:text-text-disabled data-[state=active]:border-border-interactive data-[state=active]:text-heading-compact-01 data-[state=active]:text-text-primary",
        className,
    )}
    {...restProps}
/>
