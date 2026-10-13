<script lang="ts" module>
    import { tv } from "$lib/utils.js";
    import { type VariantProps } from "tailwind-variants";

    export const emptyMediaVariants = tv({
        base: "mb-2 flex shrink-0 items-center justify-center [&_svg]:pointer-events-none [&_svg]:shrink-0",
        variants: {
            variant: {
                default: "bg-transparent",
                icon: "flex size-10 shrink-0 items-center justify-center bg-layer-01 text-icon-primary",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    });

    export type EmptyMediaVariant = VariantProps<
        typeof emptyMediaVariants
    >["variant"];
</script>

<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        class: className,
        children,
        variant = "default",
        ...restProps
    }: HTMLAttributes<HTMLDivElement> & {
        variant?: EmptyMediaVariant;
    } = $props();
</script>

<div
    data-slot="empty-icon"
    data-variant={variant}
    class={cn(emptyMediaVariants({ variant }), className)}
    {...restProps}
>
    {@render children?.()}
</div>
