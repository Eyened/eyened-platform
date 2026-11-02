<script lang="ts">
    import { Accordion as AccordionPrimitive } from "bits-ui";

    let { children, ...restProps }: AccordionPrimitive.ContentProps = $props();
</script>

<AccordionPrimitive.Content class="px-4 pt-2 pb-6 text-body-01" {...restProps}>
    {@render children?.()}
</AccordionPrimitive.Content>
