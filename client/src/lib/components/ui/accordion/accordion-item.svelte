<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { Accordion as AccordionPrimitive } from "bits-ui";

    let {
        class: className,
        children,
        ...restProps
    }: AccordionPrimitive.ItemProps = $props();
</script>

<!-- Carbon flush: 1 px dividers inset 16 px each side. -->
<AccordionPrimitive.Item
    class={cn(
        "relative border-t border-transparent before:absolute before:inset-x-4 before:-top-px before:h-px before:bg-border-subtle-01 last:border-b last:after:absolute last:after:inset-x-4 last:after:-bottom-px last:after:h-px last:after:bg-border-subtle-01 in-dialog:before:bg-border-subtle-02 in-dialog:last:after:bg-border-subtle-02",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</AccordionPrimitive.Item>
