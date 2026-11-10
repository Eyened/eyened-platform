<script lang="ts">
    import { mergeProps } from "bits-ui";
    import {
        Button,
        type ButtonProps,
    } from "$lib/components/ui/button/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import type { Snippet } from "svelte";
    import type { HTMLButtonAttributes } from "svelte/elements";

    // Carbon IconButton: ghost, 40 px (`icon-xs` 24 px); `label` is both the tooltip and the accessible name, `shortcut` follows it in the tooltip.
    // Its own Provider (Carbon's 100 ms enter delay) so it works outside Main.
    // closeOnClick=false keeps the tooltip open after a click, for Carbon's "Copied!" feedback.
    let {
        label,
        size = "icon",
        children,
        closeOnClick = true,
        shortcut,
        ...restProps
    }: Omit<HTMLButtonAttributes, "aria-label" | "children"> & {
        label: string;
        size?: "icon" | "icon-xs";
        children: Snippet;
        closeOnClick?: boolean;
        shortcut?: string;
    } = $props();
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
                    variant="ghost"
                    {size}
                    aria-label={label}
                >
                    {@render children()}
                </Button>
            {/snippet}
        </Tooltip.Trigger>
        <Tooltip.Content size="icon"
            >{label}{#if shortcut}<kbd class="ms-4 font-sans">{shortcut}</kbd
                >{/if}</Tooltip.Content
        >
    </Tooltip.Root>
</Tooltip.Provider>
