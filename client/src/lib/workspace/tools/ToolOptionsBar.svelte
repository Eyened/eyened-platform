<!--
@component
The tool options bar: the armed tool's name, its options, then a one-line hint for keys without a button. The hint drops first when the bar is short.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import ZoomIn from "carbon-icons-svelte/lib/ZoomIn.svelte";
    import ZoomOut from "carbon-icons-svelte/lib/ZoomOut.svelte";
    import { getContext } from "svelte";
    import type { Workspace } from "../workspace.svelte";
    import { NO_TOOL_HINT, toolById } from "./registry";

    const ZOOM_STEP = 1.25;

    const workspace = getContext<Workspace>("workspace");
    const tool = $derived(
        workspace.armedTool ? toolById(workspace.armedTool) : null,
    );
    const viewport = $derived(workspace.selectedViewport);
    // P names its registration; without one, the hint says what to do first.
    const point = $derived(
        tool?.id === "point" ? (viewport?.layers?.pointTarget ?? null) : null,
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

    let bar: HTMLElement | undefined = $state();
    let hintElement: HTMLElement | undefined = $state();
    let hintFits = $state(true);

    // The hint shows whole or not at all; measured again when the bar or the hint changes.
    $effect(() => {
        void hint;
        if (!bar || !hintElement) return;
        const el = hintElement;
        const measure = () => {
            hintFits = el.scrollWidth <= el.clientWidth;
        };
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(bar);
        return () => observer.disconnect();
    });
</script>

<div
    bind:this={bar}
    class="flex h-full min-w-0 items-center gap-3 ps-4 pe-2 whitespace-nowrap"
>
    {#if tool}
        <span class="text-heading-compact-01 text-text-primary"
            >{tool.name}</span
        >
    {/if}
    {#if tool?.id === "zoom"}
        <div role="group" aria-label="Zoom" class="flex items-center">
            <IconButton
                size="icon-xs"
                label="Zoom out"
                disabled={!viewport}
                onclick={() => viewport?.zoomBy(1 / ZOOM_STEP)}
            >
                <ZoomOut />
            </IconButton>
            <span
                class="w-12 text-center text-body-compact-01 text-text-primary"
                >{viewport ? `${viewport.zoomPercent}%` : "–"}</span
            >
            <IconButton
                size="icon-xs"
                label="Zoom in"
                disabled={!viewport}
                onclick={() => viewport?.zoomBy(ZOOM_STEP)}
            >
                <ZoomIn />
            </IconButton>
        </div>
    {/if}
    {#if point}
        <span class="text-body-compact-01 text-text-primary"
            >Registration [{point.id}]{point.canEdit
                ? ""
                : " · read-only"}</span
        >
    {/if}
    <span
        bind:this={hintElement}
        class="min-w-0 flex-1 overflow-hidden text-helper-text-01 text-text-secondary"
        class:invisible={!hintFits}
        aria-hidden={!hintFits}>{hint}</span
    >
</div>
