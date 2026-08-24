<script lang="ts">
    import type { EventName, ViewerModifiers, ViewerWheelData } from "./viewer-utils";
    import type { ViewerContext } from "./viewerContext.svelte";
    import { getContext, onDestroy, onMount } from "svelte";
    import { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
    import Stretch from "$lib/viewer-window/panelRendering/Stretch.svelte";
    import WindowLevel from "$lib/viewer-window/panelRendering/WindowLevel.svelte";
    import BscanLinks from "$lib/viewer-window/panelSegmentation/BscanLinks.svelte";

    export interface Props {
        showInfo?: boolean;
    }
    let { showInfo = true }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    // add viewer to viewerWindowContext
    // this registers the viewerContext for repaint callbacks
    onDestroy(viewerWindowContext.addViewer(viewerContext));

    let viewerElement: HTMLDivElement;

    // update viewingRect and canvas size on resize
    onMount(() => {
        const resizeObserver = new ResizeObserver(() => {
            const viewingRect = viewerElement.getBoundingClientRect();
            viewerContext.viewingRect = viewingRect;
            const { width, height } = viewingRect;
            viewerContext.canvas2D.width = width;
            viewerContext.canvas2D.height = height;
            viewerContext.viewerSize = { width, height };
            viewerContext.initTransform();
        });

        resizeObserver.observe(viewerElement);

        return () => resizeObserver.disconnect();
    });

    //
    onMount(() => {
        viewerElement.appendChild(viewerContext.canvas2D);
    });

    // event handling
    let cursor = {
        x: 0,
        y: 0,
    };

    let pointerDown = false;
    let modifierState: ViewerModifiers = {
        shift: false,
        ctrl: false,
        alt: false,
        meta: false,
    };

    function wheelDeltaToPixels(event: WheelEvent, value: number): number {
        switch (event.deltaMode) {
            case WheelEvent.DOM_DELTA_LINE:
                return value * 16;
            case WheelEvent.DOM_DELTA_PAGE:
                return value * window.innerHeight;
            default:
                return value;
        }
    }

    function buildModifiers(event: Event): ViewerModifiers {
        const eventWithModifiers = event as KeyboardEvent | MouseEvent | WheelEvent | PointerEvent;
        if (typeof eventWithModifiers.shiftKey === "boolean") {
            return {
                shift: modifierState.shift || eventWithModifiers.shiftKey,
                ctrl: modifierState.ctrl || eventWithModifiers.ctrlKey,
                alt: modifierState.alt || eventWithModifiers.altKey,
                meta: modifierState.meta || eventWithModifiers.metaKey,
            };
        }
        return modifierState;
    }

    function buildWheelData(event: WheelEvent, modifiers: ViewerModifiers): ViewerWheelData {
        const deltaXPx = wheelDeltaToPixels(event, event.deltaX);
        const deltaYPx = wheelDeltaToPixels(event, event.deltaY);
        const primaryDeltaPx = Math.abs(deltaYPx) > 0.001 ? deltaYPx : deltaXPx;
        return {
            deltaXPx,
            deltaYPx,
            primaryDeltaPx,
            zoomIntent: modifiers.shift || modifiers.ctrl || modifiers.meta,
        };
    }

    function updateModifierState(event: KeyboardEvent, value: boolean) {
        if (event.key === "Shift") modifierState.shift = value;
        if (event.key === "Control") modifierState.ctrl = value;
        if (event.key === "Alt") modifierState.alt = value;
        if (event.key === "Meta") modifierState.meta = value;
    }

    function resetModifierState() {
        modifierState = { shift: false, ctrl: false, alt: false, meta: false };
    }

    function forwardEvent(eventName: EventName, event: Event) {
        const position = viewerContext.viewerToImageCoordinates(cursor);
        const modifiers = buildModifiers(event);
        const wheel = event instanceof WheelEvent
            ? buildWheelData(event, modifiers)
            : undefined;
        viewerContext.forwardEvent(eventName, {
            event,
            viewerContext,
            cursor,
            position,
            modifiers,
            wheel,
        });
    }

    function onpointerenter(e: PointerEvent) {
        viewerElement.focus();
        viewerContext.active = true;
        forwardEvent("pointerenter", e);
    }

    function onpointerleave(e: PointerEvent) {
        if (!pointerDown) {
            viewerContext.active = false;
        }
        resetModifierState();
        forwardEvent("pointerleave", e);
    }

    function onpointerdown(e: PointerEvent) {
        // Capture the pointer to ensure we get all events even if the pointer moves outside the viewer until the pointer is released
        viewerElement.setPointerCapture(e.pointerId);
        pointerDown = true;
        forwardEvent("pointerdown", e);
    }

    function onpointerup(e: PointerEvent) {
        // Release the pointer
        viewerElement.releasePointerCapture(e.pointerId);
        pointerDown = false;
        forwardEvent("pointerup", e);
    }

    function onkeydown(e: KeyboardEvent) {
        updateModifierState(e, true);
        forwardEvent("keydown", e);
    }

    function onkeyup(e: KeyboardEvent) {
        updateModifierState(e, false);
        forwardEvent("keyup", e);
    }

    function onpointermove(e: PointerEvent) {
        cursor = {
            x: e.x - viewerContext.viewingRect.left,
            y: e.y - viewerContext.viewingRect.top,
        };
        forwardEvent("pointermove", e);
    }

    function onwheel(e: WheelEvent) {
        forwardEvent("wheel", e);
    }

    function ondblclick(e: MouseEvent) {
        forwardEvent("dblclick", e);
    }

    function oncontextmenu(e: MouseEvent) {
        e.preventDefault();
    }

    function onblur() {
        resetModifierState();
    }

    let index = $state({
        get value() {
            return viewerContext.index;
        },
        set value(value: number) {
            viewerContext.setIndex(value);
        },
    });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="main">
    <div
        class="viewer"
        tabindex="0"
        bind:this={viewerElement}
        {onpointerdown}
        {onpointerup}
        {onpointermove}
        {onpointerenter}
        {onpointerleave}
        {onwheel}
        {ondblclick}
        {onkeydown}
        {onkeyup}
        {onblur}
        {oncontextmenu}
    ></div>

    {#if showInfo}
        <div class="info">
            {#if viewerContext.image.is3D}
                <div>
                    <label>
                        Lock scroll
                        <input
                            type="checkbox"
                            bind:checked={viewerContext.lockScroll}
                        />
                    </label>
                </div>
                <div>
                    <input
                        type="range"
                        min="0"
                        max={viewerContext.image.depth - 1}
                        bind:value={index.value}
                    />
                    <span>{index.value}</span>
                </div>
                
            {/if}
            {#if viewerContext.image.orientation === 'axial'}
                <WindowLevel />
                <Stretch />
            {/if}
        </div>
        <div class="info">
            {#if viewerContext.image.is3D}
                <BscanLinks />
            {/if}
        </div>
    {/if}
</div>

<style>
    div.main {
        display: flex;
        flex: 1;
        position: relative;
        flex-direction: column;
        align-items: center;
    }
    div.info {
        display: flex;
        color: white;
        z-index: 1;
        flex: 0;
        align-items: center;
    }
    div.info span {
        margin: 0.5em;
        width: 3em;
        font-size: small;
        display: inline-block;
    }
    div.viewer {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        user-select: none;
        touch-action: none;
        outline: none;
        /* https://stackoverflow.com/questions/59010779/pointer-event-issue-pointercancel-with-pressure-input-pen */
    }
</style>
