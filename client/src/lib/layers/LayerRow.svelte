<!--
@component
One 24 px Layers row, one step in from its parent (depth 1 under a type, 2 under a group): an optional swatch, the name on one line (full text in a tooltip), tags, then icons at the right.
The icons keep their space at rest and show on hover, on focus inside the row and on the selected row; an icon marked data-sticky="true" shows at rest too.
-->
<script lang="ts">
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { mergeProps } from "bits-ui";
    import type { Snippet } from "svelte";
    import type { HTMLAttributes } from "svelte/elements";

    let {
        label,
        name,
        tooltip,
        nameLabel,
        selected = false,
        depth = 1,
        visible = false,
        current = false,
        pressed = true,
        onselect,
        swatch,
        tags,
        icons,
        children,
        class: className = "",
        ...rest
    }: Omit<HTMLAttributes<HTMLDivElement>, "children"> & {
        label: string;
        name: string;
        tooltip?: string;
        nameLabel?: string;
        selected?: boolean;
        /** 1 under a type, 2 under a group. Lines under the row can start at `ps-(--row-indent)`. */
        depth?: 1 | 2;
        visible?: boolean;
        /** Holds the selected viewport's image: aria-current on the name. */
        current?: boolean;
        /** False where the bar isn't a toggle, so the name isn't read as pressed. */
        pressed?: boolean;
        onselect?: () => void;
        swatch?: Snippet;
        tags?: Snippet;
        icons?: Snippet;
        children?: Snippet;
        class?: string;
    } = $props();

    const bar = $derived(
        selected
            ? "border-border-interactive bg-layer-selected-01"
            : visible
              ? "border-border-strong-01"
              : "border-transparent",
    );
</script>

<div
    {...rest}
    data-layer-row
    class="row border-s-3 {bar} {className}"
    class:selected
    style:--row-indent={depth === 2 ? "45px" : "29px"}
    role="group"
    aria-label={label}
>
    <div class="flex min-h-6 items-center gap-1 ps-(--row-indent) pe-2">
        {@render swatch?.()}
        <Tooltip.Provider delayDuration={100}>
            <Tooltip.Root>
                <Tooltip.Trigger>
                    {#snippet child({ props })}
                        {#if onselect}
                            <button
                                {...mergeProps(props, { onclick: onselect })}
                                type="button"
                                class="min-h-6 min-w-0 flex-1 truncate px-1 text-start text-body-compact-01 text-text-primary hover:bg-layer-hover-01 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                                aria-label={nameLabel}
                                aria-pressed={pressed ? selected : undefined}
                                aria-current={current ? "true" : undefined}
                                >{name}</button
                            >
                        {:else}
                            <!-- A definition-tooltip trigger: it takes focus so keyboard users can read a cut-off name, and does nothing else. -->
                            <span
                                {...props}
                                class="min-h-6 min-w-0 flex-1 truncate px-1 text-body-compact-01 text-text-primary focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                                >{name}</span
                            >
                        {/if}
                    {/snippet}
                </Tooltip.Trigger>
                <!-- A tooltip can hold several lines. -->
                <Tooltip.Content side="left" class="whitespace-pre-line"
                    >{tooltip ?? name}</Tooltip.Content
                >
            </Tooltip.Root>
        </Tooltip.Provider>
        {@render tags?.()}
        <div class="icons flex shrink-0 items-center">{@render icons?.()}</div>
    </div>
    {@render children?.()}
</div>

<style>
    /* Opacity, not visibility, so the icons keep their space and their tab stops; no pointer events, so an unseen icon takes no tap. */
    .icons > :global(*) {
        opacity: 0;
        pointer-events: none;
    }
    .row:hover .icons > :global(*),
    .row:focus-within .icons > :global(*),
    .row.selected .icons > :global(*),
    .icons > :global([data-sticky="true"]) {
        opacity: 1;
        pointer-events: auto;
    }
</style>
