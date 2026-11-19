<!--
@component
The tool options bar: the armed tool's name, a Draw tool's target or why it can't draw, its options, then a one-line hint for keys without a button. When the bar is short the hint drops first, then the segmentation name cuts with …, then trailing options move into ⋯ one at a time, last first.
-->
<script lang="ts">
    import { getContext, tick, untrack } from "svelte";
    import OverflowMenu from "../OverflowMenu.svelte";
    import type { Workspace } from "../workspace.svelte";
    import { NO_TOOL_HINT, toolById, type ToolId } from "./registry";
    import ToolOption, { type OptionId } from "./ToolOption.svelte";

    const workspace = getContext<Workspace>("workspace");
    const tool = $derived(
        workspace.armedTool ? toolById(workspace.armedTool) : null,
    );
    const viewport = $derived(workspace.selectedViewport);
    // P names its registration; without one, the hint says what to do first.
    const point = $derived(
        tool?.id === "point" ? (viewport?.layers?.pointTarget ?? null) : null,
    );
    // A Draw tool names the selected viewport's current segmentation, or says why it can't draw there.
    const draw = $derived(
        tool?.group === "Draw" ? (viewport?.layers?.drawTarget ?? null) : null,
    );
    const reason = $derived(draw?.reason ?? null);
    const fullName = $derived(
        draw?.name
            ? [draw.name.segmentation, draw.name.feature]
                  .filter(Boolean)
                  .join(" › ")
            : "",
    );
    const hint = $derived.by(() => {
        if (!tool) return NO_TOOL_HINT;
        if (tool.id !== "point") return tool.hint;
        if (!point) return "Make a registration current in Pointsets.";
        // ASSUMPTION: the spec says only "read-only" for a colleague's registration.
        return point.canEdit
            ? tool.hint
            : "Another grader's points can't be moved";
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
            default:
                return [];
        }
    }
    // A reason replaces the options. Size shows nothing without an image, so it is left out.
    const options = $derived(
        reason
            ? []
            : optionsFor(tool?.id).filter(
                  (id) =>
                      id !== "size" || viewport?.layers?.viewerContext.image,
              ),
    );
    const isHistory = (id: OptionId) => id === "undo" || id === "redo";

    let bar: HTMLElement | undefined = $state();
    let hintElement: HTMLElement | undefined = $state();
    let hintFits = $state(true);

    /** How many trailing options sit in ⋯. */
    let folds = $state(0);
    const shown = $derived(options.slice(0, options.length - folds));
    const folded = $derived(options.slice(options.length - folds));

    let fitting = 0;
    /** Starts with nothing folded, then moves the last option in the row into ⋯ until the row fits; the hint shows whole or not at all. */
    async function fit() {
        const el = bar;
        if (!el) return;
        // A newer fit replaces this one.
        const run = ++fitting;
        folds = 0;
        await tick();
        while (folds < options.length && el.scrollWidth > el.clientWidth) {
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
    class="flex h-full min-w-0 items-center gap-3 ps-4 pe-2 whitespace-nowrap"
>
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
    {#if point}
        <span class="text-body-compact-01 text-text-primary"
            >Registration [{point.id}]{point.canEdit
                ? ""
                : " · read-only"}</span
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
