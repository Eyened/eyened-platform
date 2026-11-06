<!--
@component
A viewport's bottom bar: render mode, W/L and, on B-scans, stretch. It shows the largest state that fits.
-->
<script lang="ts" module>
    import type { BarWidths } from "./viewControlsFit";

    // A type's control widths are fixed, so each is measured once.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- A plain cache; nothing reads it reactively.
    const measured = new Map<string, BarWidths>();
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { getContext, type Snippet } from "svelte";
    import { RENDER_MODE_CODES } from "./controls/hotkeys";
    import {
        barState,
        nonDefaultLabel,
        notchToStretch,
        shortStretch,
        STRETCH_NOTCHES,
        STRETCH_PRESETS,
        stretchPreset,
        stretchToNotch,
    } from "./viewControlsFit";
    import { getAvailableRenderModes, type RenderMode } from "./viewer-utils";
    import type { ViewerContext } from "./viewerContext.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { image } = viewerContext;
    const hasStretch = image.orientation === "axial";
    const colour = image.supportsColorRenderModes;
    const kind = hasStretch ? "bscan" : colour ? "colour" : "grey";

    const modes = getAvailableRenderModes(colour);
    const items = modes.map((mode) => ({
        id: mode,
        text: mode,
        hint: Object.entries(RENDER_MODE_CODES)
            .find(([, m]) => m === mode)?.[0]
            .slice(3),
    }));
    const presets = STRETCH_PRESETS.map((p) => ({
        value: String(p),
        text: String(p),
        label: `Stretch ${p}×`,
    }));

    let widths = $state(measured.get(kind) ?? null);
    let available = $state(0);
    let fullRow: HTMLElement | undefined = $state();
    let compactRow: HTMLElement | undefined = $state();
    let barElement: HTMLElement | null = $state(null);

    const shown = $derived(widths && barState(widths, available));
    const stretchText = $derived(shortStretch(viewerContext.stretch));
    const foldedLabel = $derived(
        nonDefaultLabel({
            mode: viewerContext.renderMode,
            windowLevel: viewerContext.windowLevel,
            defaultWindowLevel: viewerContext.defaultWindowLevel,
            stretch: hasStretch ? viewerContext.stretch : undefined,
            defaultStretch: viewerContext.defaultStretch,
        }),
    );

    $effect(() => {
        if (widths || !compactRow || available === 0) return;
        widths = {
            full: fullRow ? fullRow.offsetWidth : null,
            compact: compactRow.offsetWidth,
        };
        measured.set(kind, widths);
    });

    // An unavailable mode falls back to Original.
    $effect(() => {
        if (!modes.includes(viewerContext.renderMode))
            viewerContext.renderMode = "Original";
    });

    // The refit runs here, not in an effect: an effect would also refit on mount.
    function setStretch(stretch: number) {
        viewerContext.stretch = stretch;
        viewerContext.initTransform();
    }
</script>

{#snippet modeControl()}
    <div class={colour ? "w-48 flex-none" : "w-32 flex-none"}>
        <Dropdown
            {items}
            size="sm"
            hideLabel
            onclose={() => viewerContext.returnFocus()}
            direction="top"
            labelText="Render mode"
            selectedId={viewerContext.renderMode}
            onselect={(mode) => (viewerContext.renderMode = mode as RenderMode)}
        />
    </div>
{/snippet}

{#snippet windowLevelControl()}
    <div role="group" aria-label="Window / level" class="control">
        <span class="name">W/L</span>
        <Slider
            class="w-24"
            oncommit={() => viewerContext.returnFocus()}
            min={0}
            max={255}
            labels={["Window low", "Window high"]}
            values={[
                Math.round(viewerContext.windowLevel.min),
                Math.round(viewerContext.windowLevel.max),
            ]}
            onchange={([min, max]) =>
                (viewerContext.windowLevel = { min, max })}
        />
    </div>
{/snippet}

{#snippet stretchControls()}
    <div role="group" aria-label="Stretch" class="control">
        <span class="name">Stretch</span>
        <ToggleGroup
            label="Stretch presets"
            items={presets}
            value={stretchPreset(viewerContext.stretch)}
            onchange={(p) => setStretch(Number(p))}
        />
        <Slider
            class="w-24"
            oncommit={() => viewerContext.returnFocus()}
            min={0}
            max={STRETCH_NOTCHES}
            labels={["Stretch"]}
            valueTexts={[`${viewerContext.stretch.toFixed(1)}×`]}
            values={[stretchToNotch(viewerContext.stretch)]}
            onchange={([notch]) => setStretch(notchToStretch(notch))}
        />
        <span class="value">{viewerContext.stretch.toFixed(1)}×</span>
    </div>
{/snippet}

{#snippet popover(text: string, content: Snippet, folded = false)}
    <Popover.Root>
        <Popover.Trigger>
            {#snippet child({ props })}
                <!-- Stretch has a fixed minimum, so its measured width holds for every value. -->
                <Button
                    {...props}
                    variant="ghost"
                    size="sm"
                    class={folded ? undefined : "min-w-33"}
                    >{text} <ChevronDown /></Button
                >
            {/snippet}
        </Popover.Trigger>
        <!-- The folded popover opens beside the viewport, so the image stays visible while it is adjusted. -->
        <Popover.Content
            data-slot="filter-popover"
            role="dialog"
            aria-label={text}
            customAnchor={folded ? barElement : null}
            side={folded ? "right" : "top"}
            align={folded ? "end" : "start"}
            class="flex w-auto flex-col items-start gap-3 shadow-popover"
        >
            {@render content()}
        </Popover.Content>
    </Popover.Root>
{/snippet}

{#snippet stretchPopover()}
    {#if hasStretch}
        {@render popover(`Stretch ${stretchText}`, stretchControls)}
    {/if}
{/snippet}

{#snippet everyControl()}
    {@render modeControl()}
    {@render windowLevelControl()}
    {#if hasStretch}
        {@render stretchControls()}
    {/if}
{/snippet}

{#if viewerContext.renderControls}
    <div
        role="group"
        aria-label="View controls"
        class="bar viewport-overlay"
        bind:this={barElement}
        bind:clientWidth={available}
    >
        {#if !widths}
            <div class="measure" inert aria-hidden="true">
                {#if hasStretch}
                    <div class="row" data-row="full" bind:this={fullRow}>
                        {@render everyControl()}
                    </div>
                {/if}
                <div class="row" data-row="compact" bind:this={compactRow}>
                    {@render modeControl()}
                    {@render windowLevelControl()}
                    {@render stretchPopover()}
                </div>
            </div>
        {:else if shown === "full"}
            <div class="row">{@render everyControl()}</div>
        {:else if shown === "compact"}
            <div class="row">
                {@render modeControl()}
                {@render windowLevelControl()}
                {@render stretchPopover()}
            </div>
        {:else}
            <div class="row folded">
                {@render popover("View", everyControl, true)}
                <span class="value truncate" title={foldedLabel}
                    >{foldedLabel}</span
                >
            </div>
        {/if}
    </div>
{/if}

<style>
    .bar {
        position: absolute;
        inset: auto 0 0 0;
        z-index: 1;
        height: 2rem;
        overflow: hidden;
        background: var(--color-background);
    }
    .row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: max-content;
        height: 2rem;
        padding-inline: 0.5rem;
        white-space: nowrap;
    }
    .row.folded {
        width: 100%;
    }
    .measure {
        position: absolute;
        visibility: hidden;
    }
    .control {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .name,
    .value {
        font-size: var(--text-label-01);
        color: var(--color-text-secondary);
    }
    .value {
        min-width: 0;
        font-variant-numeric: tabular-nums;
    }
</style>
