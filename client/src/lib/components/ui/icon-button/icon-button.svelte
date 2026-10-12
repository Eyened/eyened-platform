<script lang="ts">
    import { mergeProps } from "bits-ui";
    import {
        Button,
        type ButtonProps,
    } from "$lib/components/ui/button/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import type { Snippet } from "svelte";
    import type { HTMLButtonAttributes } from "svelte/elements";

    // Carbon IconButton: ghost, 40 px; `label` is both the tooltip and the accessible name.
    // Its own Provider (Carbon's 100 ms enter delay) so it works outside Main.
    let {
        label,
        children,
        ...restProps
    }: Omit<HTMLButtonAttributes, "aria-label" | "children"> & {
        label: string;
        children: Snippet;
    } = $props();
</script>

<Tooltip.Provider delayDuration={100}>
    <Tooltip.Root>
        <Tooltip.Trigger>
            {#snippet child({ props })}
                <Button
                    {...mergeProps(restProps, props) as ButtonProps}
                    variant="ghost"
                    size="icon"
                    aria-label={label}
                >
                    {@render children()}
                </Button>
            {/snippet}
        </Tooltip.Trigger>
        <Tooltip.Content size="icon">{label}</Tooltip.Content>
    </Tooltip.Root>
</Tooltip.Provider>
