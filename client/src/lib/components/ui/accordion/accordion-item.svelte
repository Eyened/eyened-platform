<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { Accordion as AccordionPrimitive } from "bits-ui";

    let {
        class: className,
        children,
        ...restProps
    }: AccordionPrimitive.ItemProps = $props();
</script>

<AccordionPrimitive.Item
    class={cn(
        "border-t border-border-subtle-01 last:border-b in-dialog:border-border-subtle-02",
        className,
    )}
    {...restProps}
>
    {@render children?.()}
</AccordionPrimitive.Item>
