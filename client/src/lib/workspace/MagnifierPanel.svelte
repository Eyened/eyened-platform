<!--
@component
The Magnifier: a floating panel that shows the area under the pointer, magnified, from whichever viewport the pointer is in.
It moves only when the grader drags its gripper or clicks it for the next corner.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import { CLICK_DRAG_THRESHOLD_PX } from "$lib/viewer/tools/PointTool.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Draggable from "carbon-icons-svelte/lib/Draggable.svelte";
    import { getContext } from "svelte";
    import { titleText, type ViewportTitle } from "./imageMeta";
    import {
        clampInto,
        corners,
        MAGNIFIER_SIZES,
        MAGNIFIER_ZOOMS,
        nextCorner,
        STRIP_PX,
        type MagnifierSize,
        type MagnifierZoom,
        type Point,
    } from "./magnifier";
    import MagnifierView from "./MagnifierView.svelte";
    import type { Workspace } from "./workspace.svelte";

    let {
        width,
        height,
        titleFor,
    }: {
        /** The canvas's size, in px. */
        width: number;
        height: number;
        titleFor: (imageId: string) => ViewportTitle | null;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();

    const ZOOMS = MAGNIFIER_ZOOMS.map((z) => ({
        value: String(z),
        text: `${z}×`,
        label: `${z}×`,
    }));
    const SIZES = [
        { value: "small", text: "S", label: "Small" },
        { value: "medium", text: "M", label: "Medium" },
        { value: "large", text: "L", label: "Large" },
    ];

    const m = $derived(workspace.magnifier);
    const source = $derived(workspace.magnifierSource);
    const side = $derived(MAGNIFIER_SIZES[m.size]);
    const title = $derived.by(() => {
        if (!source) return "";
        const t = titleFor(source.viewerContext.image.image_id);
        return [
            source.position === null ? "" : `Viewport ${source.position + 1}`,
            t ? titleText(t) : "",
        ]
            .filter(Boolean)
            .join(" · ");
    });

    // One view per source viewport: a new view compiles its own shaders, and nothing deletes them.
    const views = new WeakMap<ViewerContext, ViewerContext>();
    function viewFor(from: ViewerContext): ViewerContext {
        let view = views.get(from);
        if (!view) {
            view = new ViewerContext(from.image, from.viewerWindowContext);
            views.set(from, view);
        }
        return view;
    }

    let panelWidth = $state(0);
    let panelHeight = $state(0);
    const area = $derived({ width, height });
    const panel = $derived({ width: panelWidth, height: panelHeight });
    // Below the strip and the top-right viewport's titlebar, above the bottom viewport's view bar.
    const places = $derived(
        corners(area, panel, {
            top: (workspace.strip ? STRIP_PX : 0) + 32,
            right: 16,
            bottom: 40,
            left: 16,
        }),
    );
    const stored = $derived(
        m.x === null || m.y === null ? places[0] : { x: m.x, y: m.y },
    );
    let live: Point | null = $state(null);
    const shown = $derived(live ?? clampInto(stored, area, panel));

    let press: { x: number; y: number; from: Point } | null = null;
    let dragged = false;

    function onpointerdown(e: PointerEvent) {
        // Only the main button drags.
        if (e.button > 0) return;
        (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
        press = { x: e.clientX, y: e.clientY, from: shown };
        dragged = false;
    }

    function onpointermove(e: PointerEvent) {
        if (!press) return;
        const dx = e.clientX - press.x;
        const dy = e.clientY - press.y;
        if (!dragged && Math.hypot(dx, dy) < CLICK_DRAG_THRESHOLD_PX) return;
        dragged = true;
        live = clampInto(
            { x: press.from.x + dx, y: press.from.y + dy },
            area,
            panel,
        );
    }

    function onpointerup() {
        press = null;
        if (live) workspace.setMagnifier(live);
        live = null;
    }

    // A cancelled drag (pen or touch) never gets a pointerup: drop the move and keep the stored place.
    function onpointercancel() {
        press = null;
        dragged = false;
        live = null;
    }

    // A click or Enter goes to the next corner; the click that ends a drag does not.
    function onclick() {
        if (dragged) {
            dragged = false;
            return;
        }
        workspace.setMagnifier(nextCorner(shown, places));
    }
</script>

{#if m.on}
    <section
        class="magnifier"
        class:dragging={live !== null}
        aria-labelledby="{uid}-title"
        style="left: {shown.x}px; top: {shown.y}px; width: {side + 2}px;"
        bind:offsetWidth={panelWidth}
        bind:offsetHeight={panelHeight}
    >
        <div class="flex justify-center">
            <IconButton
                label="Move magnifier to next corner"
                tooltip="Drag to move, click for next corner"
                size="icon-xs"
                class="cursor-grab touch-none"
                {onpointerdown}
                {onpointermove}
                {onpointerup}
                {onpointercancel}
                {onclick}
            >
                <Draggable />
            </IconButton>
        </div>
        <header class="flex items-center gap-2 ps-3">
            <h2
                id="{uid}-title"
                class="text-heading-compact-01 text-text-primary"
            >
                Magnifier
            </h2>
            <span
                class="min-w-0 flex-1 truncate text-label-01 text-text-secondary"
                >{title}</span
            >
            <IconButton
                label="Close magnifier"
                size="icon-xs"
                onclick={() => workspace.setMagnifier({ on: false })}
            >
                <Close />
            </IconButton>
        </header>
        <div
            class="view"
            class:dimmed={source !== null && !source.inside}
            style="width: {side}px; height: {side}px;"
            aria-hidden="true"
        >
            {#if source}
                {#key source.viewerContext}
                    <MagnifierView
                        {source}
                        view={viewFor(source.viewerContext)}
                    />
                {/key}
            {/if}
        </div>
        <footer
            class="flex flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2 text-label-01 text-text-secondary"
        >
            <span>Zoom</span>
            <ToggleGroup
                label="Zoom"
                value={String(m.zoom)}
                onchange={(v) =>
                    workspace.setMagnifier({
                        zoom: Number(v) as MagnifierZoom,
                    })}
                items={ZOOMS}
            />
            <span class="ms-auto">Size</span>
            <ToggleGroup
                label="Size"
                value={m.size}
                onchange={(v) =>
                    workspace.setMagnifier({ size: v as MagnifierSize })}
                items={SIZES}
            />
        </footer>
    </section>
{/if}

<style>
    /* S2 floating panel: over the viewports, below the overlays and menus of the frame. */
    .magnifier {
        position: absolute;
        z-index: 5;
        display: flex;
        flex-direction: column;
        background: var(--color-layer-01);
        border: 1px solid var(--color-border-subtle-01);
        box-shadow: 0 2px 6px rgb(0 0 0 / 0.3);
    }
    .magnifier.dragging {
        box-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
    }
    /* Opaque, like a viewport's empty area: it covers whatever lies below. */
    .view {
        position: relative;
        display: flex;
        background: #000;
        pointer-events: none;
    }
    .view.dimmed :global(canvas) {
        opacity: 0.5;
    }
</style>
