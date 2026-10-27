<script lang="ts">
    import { Select as SelectPrimitive } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { cn, type WithoutChild } from "$lib/utils.js";

    // Carbon Dropdown field (list-box__field), size lg; values from @carbon/styles 1.117.0
    // list-box/_list-box.scss and dropdown/_dropdown.scss. Inline: transparent, no bottom border.
    let {
        ref = $bindable(null),
        class: className,
        children,
        variant = "default",
        ...restProps
    }: WithoutChild<SelectPrimitive.TriggerProps> & {
        variant?: "default" | "inline";
    } = $props();
</script>

<SelectPrimitive.Trigger
    bind:ref
    data-slot="select-trigger"
    class={cn(
        "group/trigger relative flex h-12 cursor-pointer items-center text-left text-body-compact-01 text-text-primary disabled:cursor-not-allowed disabled:text-text-disabled",
        variant === "inline"
            ? "w-auto ps-2 pe-8 hover:bg-layer-hover-01 aria-expanded:hover:bg-transparent"
            : "w-full border-b border-border-strong-01 bg-field-01 ps-4 pe-12 hover:bg-field-hover-01 disabled:border-transparent aria-expanded:border-border-subtle-01 aria-expanded:hover:bg-field-01 in-dialog:border-border-strong-02 in-dialog:bg-field-02 in-dialog:hover:bg-field-hover-02 in-dialog:aria-expanded:border-border-subtle-02",
        className,
    )}
    {...restProps}
>
    <span class="truncate">{@render children?.()}</span>
    <ChevronDown
        aria-hidden="true"
        class={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 text-icon-primary transition-transform duration-70 group-disabled/trigger:text-icon-disabled group-aria-expanded/trigger:rotate-180",
            variant === "inline" ? "right-3" : "right-4",
        )}
    />
</SelectPrimitive.Trigger>
