<script lang="ts" module>
    import { tv } from "$lib/utils.js";
    import { type VariantProps } from "tailwind-variants";

    // Carbon inline notification, low or high contrast; values from @carbon/styles
    // notification/_inline-notification.scss. High contrast sets the inverse focus and icon
    // colours on the box, so its close button reads on the light fill.
    export const alertVariants = tv({
        base: "relative min-h-12 w-full py-3.75 pr-3.25 pl-13 [&>svg]:absolute [&>svg]:top-3.5 [&>svg]:left-3.25",
        variants: {
            variant: { destructive: "", warning: "", success: "" },
            contrast: {
                low: "border-y border-r border-l-3 text-text-primary",
                high: "border-l-3 bg-background-inverse text-text-inverse [--color-focus:var(--color-focus-inverse)] [--color-icon-primary:var(--color-icon-inverse)]",
            },
        },
        compoundVariants: [
            {
                variant: "destructive",
                contrast: "low",
                class: "border-y-support-error/40 border-r-support-error/40 border-l-support-error bg-notification-background-error [&>svg]:text-support-error",
            },
            {
                variant: "warning",
                contrast: "low",
                class: "border-y-support-warning/40 border-r-support-warning/40 border-l-support-warning bg-notification-background-warning [&>svg]:text-support-warning",
            },
            {
                variant: "success",
                contrast: "low",
                class: "border-y-support-success/40 border-r-support-success/40 border-l-support-success bg-notification-background-success [&>svg]:text-support-success",
            },
            {
                variant: "destructive",
                contrast: "high",
                class: "border-l-support-error-inverse [&>svg]:text-support-error-inverse",
            },
            {
                variant: "warning",
                contrast: "high",
                class: "border-l-support-warning-inverse [&>svg]:text-support-warning-inverse",
            },
            {
                variant: "success",
                contrast: "high",
                class: "border-l-support-success-inverse [&>svg]:text-support-success-inverse",
            },
        ],
        defaultVariants: {
            variant: "destructive",
            contrast: "low",
        },
    });

    export type AlertVariant = VariantProps<typeof alertVariants>["variant"];
    export type AlertContrast = VariantProps<typeof alertVariants>["contrast"];
</script>

<script lang="ts">
    import type { HTMLAttributes } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        variant = "destructive",
        contrast = "low",
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLDivElement>> & {
        variant?: AlertVariant;
        contrast?: AlertContrast;
    } = $props();
</script>

<div
    bind:this={ref}
    data-slot="alert"
    role="alert"
    class={cn(alertVariants({ variant, contrast }), className)}
    {...restProps}
>
    {@render children?.()}
</div>
