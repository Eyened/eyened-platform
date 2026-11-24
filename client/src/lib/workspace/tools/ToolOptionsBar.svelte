<!--
@component
The tool options bar: the armed tool's icon and name, its target or why it can't act there, its options, then Keys, which lists the keys without a button. When the bar is short the keyboard cursor's keys cut first, then the segmentation name cuts with …, then trailing options move into ⋯ one at a time, last first; Keys never folds. A form's armed point field takes the bar instead of the armed tool.
-->
<script lang="ts">
    import { getContext, tick, untrack } from "svelte";
    import { MediaQuery } from "svelte/reactivity";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { canPlaceOnViewer } from "$lib/forms/pointSchema";
    import WarningAltFilled from "carbon-icons-svelte/lib/WarningAltFilled.svelte";
    import OverflowMenu from "../OverflowMenu.svelte";
    import KeysPopover from "./KeysPopover.svelte";
    import type { Workspace } from "../workspace.svelte";
    import {
        KEYBOARD_CURSOR_KEYS,
        NO_TOOL_KEYS,
        toolById,
        type ToolId,
    } from "./registry";
    import ToolOption, { type OptionId } from "./ToolOption.svelte";

    const workspace = getContext<Workspace>("workspace");
    // Below 42rem there is no rail beside the bar: no tool cell, and the bar may wrap.
    const md = new MediaQuery("min-width: 42rem");
    const tool = $derived(
        workspace.armedTool ? toolById(workspace.armedTool) : null,
    );
    const viewport = $derived(workspace.selectedViewport);
    const layers = $derived(viewport?.layers ?? null);
    // An armed form point field takes the bar: its field and form, or why it can't place on this image.
    // ASSUMPTION: the form session wins over a palette tool armed at the same time.
    const formSession = $derived(pointArming.session);
    const formReason = $derived.by(() => {
        const image = layers?.viewerContext.image;
        if (!formSession || !image) return null;
        const gate = canPlaceOnViewer(
            formSession.analysis.coordinateSpace,
            image,
        );
        return gate.ok ? null : gate.message;
    });
    const shownTool = $derived(formSession ? toolById("point") : tool);
    // P names its pointset; without one selected, the reason says what to do first.
    const point = $derived(
        tool?.id === "point" ? (layers?.pointTarget ?? null) : null,
    );
    // A Draw tool names the selected viewport's current segmentation, or says why it can't draw there.
    const draw = $derived(
        tool?.group === "Draw" ? (layers?.drawTarget ?? null) : null,
    );
    // Place ETDRS names the grid it writes, or says why it can't.
    const etdrs = $derived(
        tool?.id === "etdrs" ? (layers?.etdrsTarget ?? null) : null,
    );
    const reason = $derived(
        formSession
            ? formReason
            : (point?.reason ??
                  draw?.reason ??
                  etdrs?.reason ??
                  (tool?.id === "circle" && layers && !layers.scale
                      ? "Set the image resolution, or show a grid in ETDRS grids."
                      : null)),
    );
    const fullName = $derived(
        draw?.name
            ? [draw.name.segmentation, draw.name.feature]
                  .filter(Boolean)
                  .join(" › ")
            : "",
    );
    const hasTarget = $derived(
        formSession
            ? !formReason
            : !!draw?.name ||
                  !!etdrs?.name ||
                  (point !== null && point.id !== null && !point.reason),
    );
    const cursorOn = $derived(layers?.viewerContext.keyboardCursor.on ?? false);
    // The armed tool's keys, or the keyboard cursor's while it is on, then those that work without a tool.
    const keyLists = $derived([
        ...(cursorOn
            ? [{ title: "Keyboard cursor", rows: KEYBOARD_CURSOR_KEYS }]
            : shownTool && shownTool.keys.length > 0
              ? [{ title: shownTool.name, rows: shownTool.keys }]
              : []),
        { title: "Without a tool", rows: NO_TOOL_KEYS },
    ]);

    /** Each tool's options, left to right. */
    function optionsFor(id: ToolId | undefined): OptionId[] {
        switch (id) {
            case "zoom":
                return ["zoom"];
            case "brush":
            case "eraser":
                return ["size", "dilateErode", "questionable", "undo", "redo"];
            case "polygon":
                return [
                    "fillErase",
                    "dilateErode",
                    "questionable",
                    "undo",
                    "redo",
                ];
            case "enhance":
                return [
                    "size",
                    "increaseDecrease",
                    "hardness",
                    "pressure",
                    "undo",
                    "redo",
                ];
            case "distance":
                return ["scale", "delete"];
            case "circle":
                return ["circleSize", "scale", "radiusFraction"];
            case "etdrs":
                return [
                    "etdrsSlot",
                    "keepGridSize",
                    "radiusFraction",
                    "delete",
                ];
            case "point":
                if (point?.id == null) return [];
                return point.canEdit ? ["pointStep", "delete"] : ["pointStep"];
            default:
                return [];
        }
    }
    // A reason replaces the options, but the circle keeps its scale and Place ETDRS its fraction, so they can be set here. Size shows nothing without an image, so it is left out.
    const options = $derived<OptionId[]>(
        formSession
            ? formReason
                ? []
                : ["pointStep"]
            : reason
              ? tool?.id === "circle"
                  ? ["scale"]
                  : tool?.id === "etdrs"
                    ? ["radiusFraction"]
                    : []
              : optionsFor(tool?.id).filter(
                    (id) => id !== "size" || layers?.viewerContext.image,
                ),
    );
    const isHistory = (id: OptionId) => id === "undo" || id === "redo";

    let bar: HTMLElement | undefined = $state();

    // A popover can't open from inside ⋯ (it closes ⋯), and Fovea | Disc edge is Place ETDRS's main control, so these never fold.
    const PINNED: OptionId[] = ["scale", "etdrsSlot"];
    const foldable = $derived(options.filter((id) => !PINNED.includes(id)));
    /** How many trailing foldable options sit in ⋯. */
    let folds = $state(0);
    const folded = $derived(foldable.slice(foldable.length - folds));
    const shown = $derived(options.filter((id) => !folded.includes(id)));

    let fitting = 0;
    /** Starts with nothing folded, then moves the last option in the row into ⋯ until the row fits. */
    async function fit() {
        const el = bar;
        if (!el) return;
        // A newer fit replaces this one.
        const run = ++fitting;
        folds = 0;
        await tick();
        while (folds < foldable.length && el.scrollWidth > el.clientWidth) {
            if (run !== fitting) return;
            folds += 1;
            await tick();
        }
    }

    // Fits again when the bar resizes or what it shows changes.
    $effect(() => {
        void options;
        void draw?.name;
        void etdrs?.name;
        void layers?.scale;
        void cursorOn;
        if (!bar) return;
        untrack(() => void fit());
        const observer = new ResizeObserver(() => void fit());
        observer.observe(bar);
        return () => observer.disconnect();
    });
</script>

{#snippet divider()}
    <span
        aria-hidden="true"
        class="my-2.5 w-px shrink-0 self-stretch bg-border-subtle-01"
    ></span>
{/snippet}

<div
    bind:this={bar}
    data-slot="tool-options"
    class="flex h-full min-w-0 items-center gap-3 pe-2 whitespace-nowrap"
    class:ps-4={!md.current}
    class:flex-wrap={!md.current}
>
    {#if md.current}
        <!-- The armed tool's icon under the rail, in its armed look; the name follows as text. -->
        <span
            aria-hidden="true"
            class="flex w-12 shrink-0 justify-center self-stretch border-e border-border-subtle-01"
        >
            {#if shownTool}<span
                    class="flex w-10 items-center justify-center selected-look"
                    ><shownTool.icon /></span
                >{/if}
        </span>
    {/if}
    {#if formSession}
        <span class="shrink-0 text-heading-compact-01 text-text-primary"
            >Form points</span
        >
    {:else if tool}
        <span class="shrink-0 text-heading-compact-01 text-text-primary"
            >{tool.name}</span
        >
    {:else}
        <span class="shrink-0 text-body-compact-01 text-text-secondary"
            >No tool armed · pick one in Tools</span
        >
    {/if}
    {#if hasTarget}
        {@render divider()}
        {#if formSession}
            {@const formTarget = [formSession.label, formSession.form]
                .filter(Boolean)
                .join(" · ")}
            <!-- Cuts with …, like the segmentation name. -->
            <span
                class="min-w-8 truncate text-body-compact-01 text-text-primary"
                title={formTarget}>{formTarget}</span
            >
        {:else if draw?.name}
            <!-- The segmentation name cuts with …; the class stays whole. -->
            <span class="flex min-w-0 items-center gap-2">
                {#if draw.color}
                    <span
                        aria-hidden="true"
                        class="size-3 shrink-0 rounded-full"
                        style:background-color={draw.color}
                    ></span>
                {/if}
                <span
                    class="min-w-8 truncate text-body-compact-01 text-text-primary"
                    title={fullName}>{draw.name.segmentation}</span
                >
                {#if draw.name.feature}
                    <span aria-hidden="true" class="text-text-secondary">›</span
                    >
                    <span
                        class="shrink-0 text-body-compact-01 text-text-primary"
                        title={fullName}>{draw.name.feature}</span
                    >
                {/if}
            </span>
        {:else if etdrs?.name}
            <span
                class="min-w-8 truncate text-body-compact-01 text-text-primary"
                title={etdrs.name}>{etdrs.name}</span
            >
        {:else if point && point.id !== null}
            <span class="text-body-compact-01 text-text-primary"
                >Registration {point.id}{point.canEdit
                    ? ""
                    : " · read-only"}</span
            >
        {/if}
    {/if}
    {#if cursorOn}
        <!-- Cuts first when the bar is short. -->
        <span
            class="min-w-0 shrink-[100] truncate text-helper-text-01 text-text-secondary"
            >arrows move · Space clicks · Esc leaves</span
        >
    {/if}
    {#if reason || shown.length > 0 || folded.length > 0}
        {@render divider()}
    {/if}
    <!-- Always mounted, so screen readers announce a new reason. -->
    <span
        role="status"
        class="flex min-w-0 items-center gap-2 py-1 text-body-compact-01 whitespace-normal text-text-primary"
        class:sr-only={!reason}
        >{#if reason}<WarningAltFilled
                aria-hidden="true"
                class="shrink-0 text-support-warning"
            />{/if}{reason ?? ""}</span
    >
    {#each shown.filter((id) => !isHistory(id)) as id (id)}
        <span data-option={id} class="flex shrink-0 items-center"
            ><ToolOption {id} {viewport} /></span
        >
    {/each}
    <!-- Undo and Redo are one group, like Zoom's buttons. -->
    {#if shown.some(isHistory)}
        <div
            role="group"
            aria-label="History"
            class="flex shrink-0 items-center"
        >
            {#each shown.filter(isHistory) as id (id)}
                <span data-option={id} class="flex items-center"
                    ><ToolOption {id} {viewport} /></span
                >
            {/each}
        </div>
    {/if}
    {#if folded.length}
        <OverflowMenu label="More" size="icon-xs">
            {#each folded as id (id)}
                <div data-option={id} class="flex items-center px-2 py-1">
                    <ToolOption {id} {viewport} />
                </div>
            {/each}
        </OverflowMenu>
    {/if}
    <div class="ms-auto flex shrink-0">
        <KeysPopover lists={keyLists} iconOnly={!md.current} />
    </div>
</div>
