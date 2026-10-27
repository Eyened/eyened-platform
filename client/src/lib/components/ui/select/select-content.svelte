<script lang="ts">
    import { Select as SelectPrimitive } from "bits-ui";
    import { cn, type WithoutChild } from "$lib/utils.js";

    // Carbon Dropdown menu (list-box__menu): directly below the field, 5.5 items tall, as wide as
    // the field (inline: 288–480 px). Portalled to <body>, so it keeps the 01 set inside a dialog.
    let {
        ref = $bindable(null),
        class: className,
        variant = "default",
        portalProps,
        children,
        ...restProps
    }: WithoutChild<SelectPrimitive.ContentProps> & {
        portalProps?: SelectPrimitive.PortalProps;
        variant?: "default" | "inline";
    } = $props();
</script>

<SelectPrimitive.Portal {...portalProps}>
    <SelectPrimitive.Content
        bind:ref
        sideOffset={0}
        data-slot="select-content"
        data-dropdown={variant}
        class={cn(
            "z-50 max-h-66 overflow-y-auto bg-layer-01 shadow-popover",
            variant === "inline"
                ? "max-w-120 min-w-72"
                : "w-(--bits-select-anchor-width)",
            className,
        )}
        {...restProps}
    >
        <SelectPrimitive.Viewport>
            {@render children?.()}
        </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
</SelectPrimitive.Portal>
