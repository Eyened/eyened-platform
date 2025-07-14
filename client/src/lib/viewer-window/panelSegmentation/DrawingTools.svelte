<script lang="ts">
    import { getContext, onDestroy } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import {
        Enhance,
        Polygon,
        Brush,
        ErodeDilate,
        Questionable,
        PanelIcon,
        Undo,
        Redo,
    } from "../icons/icons";

    import Toggle from "$lib/Toggle.svelte";
    import BrushradiusControl from "./BrushradiusControl.svelte";
    import { PolygonTool } from "$lib/viewer/tools/Polygon";
    import { BrushTool } from "$lib/viewer/tools/Brush";
    import { EnhanceTool } from "$lib/viewer/tools/Enhance.svelte";

    import type { SegmentationTool } from "$lib/viewer/tools/segmentation";
    import type {
        PaintSettings,
        ProbabilitySegmentation,
    } from "$lib/webgl/segmentation";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const image = viewerContext.image;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const { segmentationContext } = segmentationOverlay;
    let activeTool: undefined | SegmentationTool = $state(undefined);
    let removeTool = () => {};

    let panelActive = $derived(viewerContext.activePanels.has("Segmentation"));

    $effect(() => {
        if (!panelActive) {
            removeTool();
            activeTool = undefined;
        }
    });

    let lock = viewerContext.lockScroll;
    function activate(tool: SegmentationTool) {
        removeTool();
        if (activeTool === tool) {
            activeTool = undefined;
            removeTool = () => {};
            viewerContext.lockScroll = lock;
            return;
        }
        activeTool = tool;
        lock = viewerContext.lockScroll;
        viewerContext.lockScroll = true;
        console.log("activate", tool);
        removeTool = viewerContext.addOverlay(tool);
    }
    onDestroy(() => {
        segmentationContext.erodeDilateActive = false;
        segmentationContext.questionableActive = false;
        removeTool();
    });

    const drawingExecutor = {
        getCtx: () => image.getDrawingCtx(),
        draw: async (
            ctx: CanvasRenderingContext2D,
            mode: "paint" | "erase",
        ) => {
            const paintSettings: PaintSettings = {
                paint: mode == "paint",
                dilateErode: segmentationContext.erodeDilateActive,
                questionable: segmentationContext.questionableActive,
                activeIndices: segmentationContext.activeIndices,
            };
            try {
                await segmentationContext.segmentationItem?.draw(
                    viewerContext.index,
                    ctx.canvas,
                    paintSettings,
                );
            } catch (e) {
                console.error(e);
                console.error("Cannot draw on segmentation");
            }
        },
    };
    const brush = new BrushTool(
        drawingExecutor,
        viewerContext,
        segmentationContext,
    );
    const polygon = new PolygonTool(
        drawingExecutor,
        viewerContext,
        segmentationContext,
    );
    const enhance = new EnhanceTool(
        drawingExecutor,
        viewerContext,
        segmentationContext,
    );
    function toggle(key: "erodeDilateActive" | "questionableActive") {
        segmentationContext[key] = !segmentationContext[key];
    }

    function undo() {
        segmentationContext.segmentationItem?.undo(viewerContext.index);
    }

    function redo() {
        segmentationContext.segmentationItem?.redo(viewerContext.index);
    }

    let canUndo = $derived(
        segmentationContext.segmentationItem?.canUndo(viewerContext.index),
    );
    let canRedo = $derived(
        segmentationContext.segmentationItem?.canRedo(viewerContext.index),
    );
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="main">
    <div>
        <PanelIcon
            onclick={() => activate(brush)}
            active={activeTool == brush}
            tooltip="Brush"
            Icon={Brush}
        />

        <PanelIcon
            onclick={() => activate(polygon)}
            active={activeTool == polygon}
            tooltip="Polygon"
            Icon={Polygon}
        />

        {#if enhance}
            <PanelIcon
                onclick={() => activate(enhance)}
                active={activeTool == enhance}
                tooltip="Enhance"
                Icon={Enhance}
            />
        {:else}
            <PanelIcon
                active={segmentationContext.erodeDilateActive}
                onclick={() => toggle("erodeDilateActive")}
                tooltip="Dilate / Erode"
                Icon={ErodeDilate}
            />
        {/if}
        <PanelIcon
            active={segmentationContext.questionableActive}
            onclick={() => toggle("questionableActive")}
            tooltip="Questionable"
            Icon={Questionable}
        />
        <div class="undo-redo">
            <PanelIcon
                onclick={undo}
                tooltip="Undo"
                disabled={!$canUndo}
                Icon={Undo}
            />
            <PanelIcon
                onclick={redo}
                tooltip="Redo"
                disabled={!$canRedo}
                Icon={Redo}
            />
        </div>
    </div>

    {#if activeTool && activeTool.brushRadius !== undefined}
        <div>
            <BrushradiusControl {segmentationContext} />
        </div>
    {/if}
    {#if enhance && activeTool === enhance}
        <div class="controls">
            <label>
                <span>Hardness {enhance.hardness}</span>
                <input
                    type="range"
                    bind:value={enhance.hardness}
                    min="0"
                    max="1"
                    step="0.01"
                />
            </label>

            <label>
                <span>Pressure {enhance.pressure}</span>
                <input
                    type="range"
                    bind:value={enhance.pressure}
                    min="0"
                    max="1"
                    step="0.01"
                />
            </label>
            <div>
                <Toggle
                    textOff="Enhance"
                    textOn="Paint"
                    bind:control={enhance.enhance}
                />
            </div>
        </div>
    {/if}
    <div class="erase">
        <Toggle
            textOff="Drawing"
            textOn="Erasing"
            bind:control={segmentationContext.flipDrawErase}
        />
    </div>
</div>

<style>
    div {
        display: flex;
    }
    div.main {
        font-size: small;
        padding: 0.2em;
        background-color: rgba(255, 255, 255, 0.1);
    }
    div.main {
        flex-direction: column;
    }
    div.erase {
        flex-direction: row;
        justify-content: center;
    }
    div.undo-redo {
        border-left: 1px solid rgba(255, 255, 255, 0.5);
    }
    div.controls {
        display: flex;
        flex-direction: column;
    }
    label {
        display: flex;
        flex-direction: column;
    }
</style>
