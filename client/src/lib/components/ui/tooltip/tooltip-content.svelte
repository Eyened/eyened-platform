<script lang="ts">
    import { Tooltip as TooltipPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    // Carbon tooltip: high contrast, no shadow; values from @carbon/styles 1.117.0
    // tooltip/_tooltip.scss and popover/_popover.scss. `size="icon"` is the icon-button tooltip.
    // Defers outside clicks so an open popover still closes when its tooltip trigger is clicked.
    let {
        ref = $bindable(null),
        class: className,
        sideOffset,
        side = "top",
        size = "default",
        children,
        ...restProps
    }: TooltipPrimitive.ContentProps & { size?: "default" | "icon" } = $props();

    const icon = $derived(size === "icon");
</script>

<TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
        bind:ref
        data-slot="tooltip-content"
        sideOffset={sideOffset ?? (icon ? 8 : 12)}
        {side}
        interactOutsideBehavior="defer-otherwise-close"
        class={cn(
            "z-50 w-fit max-w-72 animate-in rounded-tooltip bg-background-inverse text-text-inverse fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            icon ? "px-4 py-0.5 text-body-compact-01" : "p-4 text-body-01",
            className,
        )}
        {...restProps}
    >
        {@render children?.()}
        <TooltipPrimitive.Arrow
            class="text-background-inverse"
            width={icon ? 8 : 12}
            height={icon ? 4 : 6}
        />
    </TooltipPrimitive.Content>
</TooltipPrimitive.Portal>
