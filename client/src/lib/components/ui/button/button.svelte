<script lang="ts" module>
    import type { ResolvedPathname } from "$app/types";
    import { cn, tv, type WithElementRef } from "$lib/utils.js";
    import type {
        HTMLAnchorAttributes,
        HTMLButtonAttributes,
    } from "svelte/elements";
    import { type VariantProps } from "tailwind-variants";

    // Carbon Button; values from @carbon/styles button/_button.scss.
    export const buttonVariants = tv({
        base: "relative inline-flex max-w-80 shrink-0 cursor-pointer items-center justify-between gap-2 border border-transparent pr-15.75 pl-3.75 text-left text-body-compact-01 focus-visible:border-focus focus-visible:shadow-button-focus disabled:cursor-not-allowed aria-disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 [&>svg]:absolute [&>svg]:right-4",
        variants: {
            variant: {
                default:
                    "bg-button-primary text-text-on-color hover:bg-button-primary-hover active:bg-button-primary-active disabled:border-button-disabled disabled:bg-button-disabled disabled:text-text-on-color-disabled aria-disabled:border-button-disabled aria-disabled:bg-button-disabled aria-disabled:text-text-on-color-disabled",
                destructive:
                    "bg-button-danger-primary text-text-on-color hover:bg-button-danger-hover active:bg-button-danger-active disabled:border-button-disabled disabled:bg-button-disabled disabled:text-text-on-color-disabled aria-disabled:border-button-disabled aria-disabled:bg-button-disabled aria-disabled:text-text-on-color-disabled",
                outline:
                    "border-button-tertiary bg-transparent text-button-tertiary hover:bg-button-tertiary-hover hover:text-text-inverse focus-visible:bg-button-tertiary focus-visible:text-text-inverse active:border-transparent active:bg-button-tertiary-active active:text-text-inverse disabled:border-button-disabled disabled:bg-transparent disabled:text-text-disabled aria-disabled:border-button-disabled aria-disabled:bg-transparent aria-disabled:text-text-disabled",
                secondary:
                    "bg-button-secondary text-text-on-color hover:bg-button-secondary-hover active:bg-button-secondary-active disabled:border-button-disabled disabled:bg-button-disabled disabled:text-text-on-color-disabled aria-disabled:border-button-disabled aria-disabled:bg-button-disabled aria-disabled:text-text-on-color-disabled",
                ghost: "bg-transparent pr-3.75 text-link-primary hover:bg-background-hover hover:text-link-primary-hover active:bg-background-active active:text-link-primary-hover disabled:bg-transparent disabled:text-text-disabled aria-disabled:bg-transparent aria-disabled:text-text-disabled [&_svg]:text-icon-primary disabled:[&_svg]:text-icon-disabled aria-disabled:[&_svg]:text-icon-disabled [&>svg]:static",
                link: "text-link-primary hover:text-link-primary-hover hover:underline disabled:text-text-disabled aria-disabled:text-text-disabled",
            },
            size: {
                default: "min-h-10 py-2.5",
                sm: "min-h-8 py-1.5",
                lg: "min-h-12 py-3.5",
                icon: "size-10 justify-center p-0 [&>svg]:static",
            },
        },
        compoundVariants: [
            {
                variant: "link",
                class: "min-h-0 border-0 p-0 focus-visible:shadow-none focus-visible:outline-1 focus-visible:outline-focus",
            },
        ],
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    });

    export type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];
    export type ButtonSize = VariantProps<typeof buttonVariants>["size"];

    export type ButtonProps = WithElementRef<HTMLButtonAttributes> &
        WithElementRef<Omit<HTMLAnchorAttributes, "href">> & {
            variant?: ButtonVariant;
            size?: ButtonSize;
            // Narrowed from HTMLAnchorAttributes' `string`: callers must pass a
            // resolve()d path, which the eslint-disable below relies on.
            href?: ResolvedPathname;
        };
</script>

<script lang="ts">
    let {
        class: className,
        variant = "default",
        size = "default",
        ref = $bindable(null),
        href = undefined,
        type = "button",
        disabled,
        children,
        ...restProps
    }: ButtonProps = $props();
</script>

{#if href}
    <!-- eslint-disable svelte/no-navigation-without-resolve -- href is typed ResolvedPathname, so callers can only supply a resolve()d path; the prop crosses a component boundary so static analysis can't trace it -->
    <a
        bind:this={ref}
        data-slot="button"
        class={cn(buttonVariants({ variant, size }), className)}
        href={disabled ? undefined : href}
        aria-disabled={disabled}
        role={disabled ? "link" : undefined}
        tabindex={disabled ? -1 : undefined}
        {...restProps}
    >
        {@render children?.()}
    </a>
    <!-- eslint-enable svelte/no-navigation-without-resolve -->
{:else}
    <button
        bind:this={ref}
        data-slot="button"
        class={cn(buttonVariants({ variant, size }), className)}
        {type}
        {disabled}
        {...restProps}
    >
        {@render children?.()}
    </button>
{/if}
