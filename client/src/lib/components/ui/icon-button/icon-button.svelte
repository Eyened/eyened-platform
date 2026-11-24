<script lang="ts">
    import { mergeProps } from "bits-ui";
    import {
        Button,
        type ButtonProps,
    } from "$lib/components/ui/button/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import type { Snippet } from "svelte";
    import type { HTMLButtonAttributes } from "svelte/elements";

    // Carbon IconButton: ghost, secondary or primary, 40 px (`icon-xs` 24 px); `label` is both the tooltip and the accessible name, `shortcut` follows it in the tooltip.
    // Its own Provider (Carbon's 100 ms enter delay) so it works outside Main.
    // closeOnClick=false keeps the tooltip open after a click, for Carbon's "Copied!" feedback.
    let {
        label,
        size = "icon",
        variant = "ghost",
        children,
        closeOnClick = true,
        shortcut,
        tooltip,
        description,
        ...restProps
    }: Omit<HTMLButtonAttributes, "aria-label" | "children"> & {
        label: string;
        size?: "icon" | "icon-xs";
        variant?: "ghost" | "secondary" | "primary";
        children: Snippet;
        closeOnClick?: boolean;
        shortcut?: string;
        /** Tooltip text when it differs from the name, e.g. "Copied" feedback. */
        tooltip?: string;
        /** A second tooltip line, e.g. what a tool does; also the button's accessible description. */
        description?: string;
    } = $props();
    const uid = $props.id();
</script>

<Tooltip.Provider delayDuration={100}>
    <Tooltip.Root disableCloseOnTriggerClick={!closeOnClick}>
        <Tooltip.Trigger>
            {#snippet child({ props })}
                <!-- Set after the spread: the trigger's tabindex 0 would otherwise replace a passed tabindex. -->
                <Button
                    {...mergeProps(restProps, props) as ButtonProps}
                    tabindex={restProps.tabindex ??
                        (props.tabindex as number | undefined)}
                    variant={variant === "primary" ? "default" : variant}
                    {size}
                    aria-label={label}
                    aria-describedby={description
                        ? `${uid}-description`
                        : (props["aria-describedby"] as string | undefined)}
                >
                    {@render children()}
                </Button>
            {/snippet}
        </Tooltip.Trigger>
        <Tooltip.Content size="icon"
            >{tooltip ?? label}{#if shortcut}<kbd class="ms-4 font-sans"
                    >{shortcut}</kbd
                >{/if}{#if description}<span
                    class="block pb-1 text-helper-text-01">{description}</span
                >{/if}</Tooltip.Content
        >
    </Tooltip.Root>
    <!-- The description on focus, before the tooltip opens; hidden elements still describe. -->
    {#if description}<span id="{uid}-description" hidden>{description}</span
        >{/if}
</Tooltip.Provider>
