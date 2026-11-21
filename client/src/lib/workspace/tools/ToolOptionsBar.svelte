<!--
@component
The tool options bar: the armed tool's name, its target or why it can't act there, its options, then a one-line hint for keys without a button. When the bar is short the hint drops first, then the segmentation name cuts with …, then trailing options move into ⋯ one at a time, last first.
-->
<script lang="ts">
    import { getContext, tick, untrack } from "svelte";
    import { MediaQuery } from "svelte/reactivity";
    import OverflowMenu from "../OverflowMenu.svelte";
    import type { Workspace } from "../workspace.svelte";
    import {
        KEYBOARD_CURSOR_HINT,
        NO_TOOL_HINT,
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
        point?.reason ??
            draw?.reason ??
            etdrs?.reason ??
            (tool?.id === "circle" && layers && !layers.scale
                ? "Set the image resolution, or show a grid in ETDRS grids."
                : null),
    );
    const fullName = $derived(
        draw?.name
            ? [draw.name.segmentation, draw.name.feature]
                  .filter(Boolean)
                  .join(" › ")
            : "",
    );
    const hint = $derived.by(() => {
        // Point's reasons it can't act stay visible; the keyboard cursor's keys replace any other hint.
        // ASSUMPTION: the spec says only "read-only" for a colleague's registration.
        if (
            tool?.id === "point" &&
            point?.id != null &&
            !point.reason &&
            !point.canEdit
        )
            return "Another grader's points can't be moved";
        if (layers?.viewerContext.keyboardCursor.on)
            return KEYBOARD_CURSOR_HINT;
        if (!tool) return NO_TOOL_HINT;
        return tool.hint;
    });

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
        reason
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
    let hintElement: HTMLElement | undefined = $state();
    let hintFits = $state(true);

    // A popover can't open from inside ⋯ (it closes ⋯), and Fovea | Disc edge is Place ETDRS's main control, so these never fold.
    const PINNED: OptionId[] = ["scale", "etdrsSlot"];
    const foldable = $derived(options.filter((id) => !PINNED.includes(id)));
    /** How many trailing foldable options sit in ⋯. */
    let folds = $state(0);
    const folded = $derived(foldable.slice(foldable.length - folds));
    const shown = $derived(options.filter((id) => !folded.includes(id)));

    let fitting = 0;
    /** Starts with nothing folded, then moves the last option in the row into ⋯ until the row fits; the hint shows whole or not at all. */
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
        if (run !== fitting) return;
        if (hintElement)
            hintFits = hintElement.scrollWidth <= hintElement.clientWidth;
    }

    // Fits again when the bar resizes or what it shows changes.
    $effect(() => {
        void options;
        void draw?.name;
        void etdrs?.name;
        void layers?.scale;
        void hint;
        if (!bar) return;
        untrack(() => void fit());
        const observer = new ResizeObserver(() => void fit());
        observer.observe(bar);
        return () => observer.disconnect();
    });
</script>

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
            {#if tool}<span
                    class="flex w-10 items-center justify-center selected-look"
                    ><tool.icon /></span
                >{/if}
        </span>
    {/if}
    {#if tool}
        <span class="shrink-0 text-heading-compact-01 text-text-primary"
            >{tool.name}</span
        >
    {/if}
    {#if draw?.name}
        <!-- The segmentation name cuts with …; the class stays whole. -->
        <span
            class="min-w-8 truncate text-body-compact-01 text-text-primary"
            title={fullName}>{draw.name.segmentation}</span
        >
        {#if draw.name.feature}
            <span aria-hidden="true" class="-ms-2 text-text-secondary">›</span>
            <span
                class="-ms-2 shrink-0 text-body-compact-01 text-text-primary"
                title={fullName}>{draw.name.feature}</span
            >
        {/if}
    {/if}
    {#if etdrs?.name}
        <span
            class="min-w-8 truncate text-body-compact-01 text-text-primary"
            title={etdrs.name}>{etdrs.name}</span
        >
    {/if}
    {#if point && point.id !== null && !point.reason}
        <span class="text-body-compact-01 text-text-primary"
            >Registration {point.id}{point.canEdit ? "" : " · read-only"}</span
        >
    {/if}
    <!-- Always mounted, so screen readers announce a new reason. -->
    <span
        role="status"
        class="min-w-0 py-1 text-body-compact-01 whitespace-normal text-text-primary"
        class:sr-only={!reason}>{reason ?? ""}</span
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
    <span
        bind:this={hintElement}
        class="min-w-0 flex-1 overflow-hidden text-helper-text-01 text-text-secondary"
        class:invisible={!hintFits}
        aria-hidden={!hintFits}>{hint}</span
    >
</div>
