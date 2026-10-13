<script lang="ts" module>
    import { tv } from "$lib/utils.js";
    import { type VariantProps } from "tailwind-variants";

    // Carbon inline notification, low contrast; values from @carbon/styles
    // notification/_inline-notification.scss.
    export const alertVariants = tv({
        base: "relative min-h-12 w-full py-3.75 pr-3.25 pl-13 text-text-primary [&>svg]:absolute [&>svg]:top-3.5 [&>svg]:left-3.25",
        variants: {
            variant: {
                destructive:
                    "border-y border-r border-l-3 border-y-support-error/40 border-r-support-error/40 border-l-support-error bg-notification-background-error [&>svg]:text-support-error",
            },
        },
        defaultVariants: {
            variant: "destructive",
        },
    });

    export type AlertVariant = VariantProps<typeof alertVariants>["variant"];
</script>

<script lang="ts">
    import type { HTMLAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        variant = "destructive",
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLDivElement>> & {
        variant?: AlertVariant;
    } = $props();
</script>

<div
    bind:this={ref}
    data-slot="alert"
    role="alert"
    class={cn(alertVariants({ variant }), className)}
    {...restProps}
>
    {@render children?.()}
</div>
