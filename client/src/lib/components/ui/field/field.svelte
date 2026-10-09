<script lang="ts" module>
    import { tv } from "$lib/utils.js";
    import { type VariantProps } from "tailwind-variants";

    export const fieldVariants = tv({
        base: "group/field flex w-full",
        variants: {
            orientation: {
                vertical: "flex-col gap-2",
                horizontal: "flex-row items-center gap-2",
            },
        },
        defaultVariants: {
            orientation: "vertical",
        },
    });

    export type FieldOrientation = VariantProps<
        typeof fieldVariants
    >["orientation"];
</script>

<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        class: className,
        orientation = "vertical",
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLDivElement>> & {
        orientation?: FieldOrientation;
    } = $props();
</script>

<div
    bind:this={ref}
    role="group"
    data-slot="field"
    data-orientation={orientation}
    class={cn(fieldVariants({ orientation }), className)}
    {...restProps}
>
    {@render children?.()}
</div>
