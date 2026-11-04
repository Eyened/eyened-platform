<!--
@component
An APG window splitter between two viewport tracks: drag it, or click to pick it up and click again to place it (WCAG 2.5.7).
-->
<script lang="ts">
    import { onDestroy } from "svelte";
    import type { Axis } from "./workspaceRules";

    let {
        axis,
        label,
        controls,
        valueNow,
        valueMin,
        valueMax,
        style,
        ondragstart,
        ondrag,
        ondragend,
        oncancel,
        onstep,
        onlimit,
        onreset,
    }: {
        axis: Axis;
        label: string;
        controls: string;
        valueNow: number;
        valueMin: number;
        valueMax: number;
        style: string;
        ondragstart: () => void;
        ondrag: (deltaPx: number) => void;
        ondragend: () => void;
        oncancel: () => void;
        onstep: (direction: -1 | 1) => void;
        onlimit: (end: "min" | "max") => void;
        onreset: () => void;
    } = $props();

    const descriptionId = $props.id();
    const DRAG_THRESHOLD_PX = 3;
    type Point = { x: number; y: number };

    let press: Point | null = null;
    let dragging = false;
    let pickedUp = $state(false);
    let pickPoint: Point = { x: 0, y: 0 };

    const offset = (e: PointerEvent, from: Point) =>
        axis === "col" ? e.clientX - from.x : e.clientY - from.y;

    function onpointerdown(e: PointerEvent) {
        if (pickedUp) return;
        (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
        press = { x: e.clientX, y: e.clientY };
        dragging = false;
    }

    function onpointermove(e: PointerEvent) {
        if (!press) return;
        const d = offset(e, press);
        if (!dragging && Math.abs(d) < DRAG_THRESHOLD_PX) return;
        if (!dragging) {
            dragging = true;
            ondragstart();
        }
        ondrag(d);
    }

    function onpointerup() {
        if (!press) return;
        const from = press;
        const wasDragging = dragging;
        press = null;
        dragging = false;
        if (wasDragging) {
            ondragend();
            return;
        }
        pickPoint = from;
        pickedUp = true;
        ondragstart();
    }

    function place() {
        pickedUp = false;
        ondragend();
    }

    function cancel() {
        if (!pickedUp) return;
        pickedUp = false;
        oncancel();
    }

    function onkeydown(e: KeyboardEvent) {
        if (e.key === "Escape" || e.key === "Tab") {
            if (!pickedUp) return;
            if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
            }
            cancel();
            return;
        }
        const back = axis === "col" ? "ArrowLeft" : "ArrowUp";
        const forward = axis === "col" ? "ArrowRight" : "ArrowDown";
        if (e.key === back) onstep(-1);
        else if (e.key === forward) onstep(1);
        else if (e.key === "Home") onlimit("min");
        else if (e.key === "End") onlimit("max");
        else if (e.key === "Enter") onreset();
        else return;
        e.preventDefault();
    }

    onDestroy(cancel);
</script>

<!-- A focusable separator is a widget (APG window splitter), so it takes keys and pointer events. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div
    role="separator"
    tabindex="0"
    aria-orientation={axis === "col" ? "vertical" : "horizontal"}
    aria-label={label}
    aria-controls={controls}
    aria-valuenow={valueNow}
    aria-valuemin={valueMin}
    aria-valuemax={valueMax}
    aria-describedby={descriptionId}
    class="splitter"
    class:col={axis === "col"}
    class:picked={pickedUp}
    {style}
    {onpointerdown}
    {onpointermove}
    {onpointerup}
    {onkeydown}
    onblur={cancel}
></div>
<span id={descriptionId} hidden>
    Drag, or click to pick up and click again to place. Arrow keys move it;
    Enter resets it.
</span>
{#if pickedUp}
    <!-- Covers the grid so no viewport takes the pointer. Pressing it keeps focus on the splitter; a click outside the grid blurs it and cancels. -->
    <div
        class="pickup"
        class:col={axis === "col"}
        data-testid="splitter-pickup"
        aria-hidden="true"
        onmousedown={(e) => e.preventDefault()}
        onpointermove={(e) => ondrag(offset(e, pickPoint))}
        onclick={place}
    ></div>
{/if}

<style>
    .splitter {
        position: absolute;
        z-index: 2;
        touch-action: none;
        outline: none;
        height: 8px;
        cursor: row-resize;
    }
    .splitter.col {
        height: auto;
        width: 8px;
        cursor: col-resize;
    }
    .splitter::after {
        content: "";
        position: absolute;
        inset: 3px 0;
    }
    .splitter.col::after {
        inset: 0 3px;
    }
    .splitter:hover::after,
    .splitter.picked::after {
        background: var(--color-border-interactive);
    }
    .splitter:focus-visible::after {
        background: var(--color-focus);
    }
    .pickup {
        position: absolute;
        inset: 0;
        z-index: 50;
        cursor: row-resize;
    }
    .pickup.col {
        cursor: col-resize;
    }
</style>
