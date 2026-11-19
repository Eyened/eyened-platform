<!--
@component
One options-bar control by id. The bar shows it in its row, or in ⋯ when the row is short; it works the same in both.
-->
<script lang="ts" module>
    export type OptionId =
        | "zoom"
        | "size"
        | "fillErase"
        | "increaseDecrease"
        | "dilateErode"
        | "questionable"
        | "hardness"
        | "pressure"
        | "undo"
        | "redo";
</script>

<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import ErodeDilate from "$lib/viewer-window/icons/ErodeDilate.svelte";
    import Questionable from "$lib/viewer-window/icons/Questionable.svelte";
    import Redo from "carbon-icons-svelte/lib/Redo.svelte";
    import Undo from "carbon-icons-svelte/lib/Undo.svelte";
    import ZoomIn from "carbon-icons-svelte/lib/ZoomIn.svelte";
    import ZoomOut from "carbon-icons-svelte/lib/ZoomOut.svelte";
    import { getContext } from "svelte";
    import { SIZE_MAX, SIZE_MIN, sizeKey } from "../paint";
    import type { ViewportHandle, Workspace } from "../workspace.svelte";

    let { id, viewport }: { id: OptionId; viewport: ViewportHandle | null } =
        $props();

    const ZOOM_STEP = 1.25;
    // The size slider runs in even steps on a log scale, since bits-ui snaps to its step grid.
    const SIZE_STEPS = 500;
    const LOG_MIN = Math.log(SIZE_MIN);
    const LOG_SPAN = Math.log(SIZE_MAX) - LOG_MIN;
    const toStep = (size: number) =>
        Math.round(((Math.log(size) - LOG_MIN) / LOG_SPAN) * SIZE_STEPS);
    const fromStep = (step: number) =>
        Math.exp(LOG_MIN + (step / SIZE_STEPS) * LOG_SPAN);

    const workspace = getContext<Workspace>("workspace");
    const layers = $derived(viewport?.layers);
    const image = $derived(layers?.viewerContext.image);
    const size = $derived(image ? workspace.paint[sizeKey(image)] : null);
    const index = $derived(layers?.viewerContext.index ?? 0);
    const segmentation = $derived(
        layers?.mainViewerContext.segmentationContext,
    );
    const canUndo = $derived(segmentation?.canUndo(index) ?? false);
    const canRedo = $derived(segmentation?.canRedo(index) ?? false);

    // After a mouse click the keys go back to the image; keyboard users stay on the control.
    function done() {
        layers?.viewerContext.returnFocus();
    }
</script>

{#if id === "zoom"}
    <div role="group" aria-label="Zoom" class="flex items-center">
        <IconButton
            size="icon-xs"
            label="Zoom out"
            disabled={!viewport}
            onclick={() => viewport?.zoomBy(1 / ZOOM_STEP)}
        >
            <ZoomOut />
        </IconButton>
        <span class="w-12 text-center text-body-compact-01 text-text-primary"
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
{:else if id === "size" && image && size !== null}
    <div class="flex items-center gap-2">
        <span class="text-label-01 text-text-secondary" title="Size  [ ]"
            >Size</span
        >
        <Slider
            class="w-24"
            values={[toStep(size)]}
            min={0}
            max={SIZE_STEPS}
            onchange={(v) => workspace.setSize(image, fromStep(v[0]))}
            oncommit={done}
            labels={["Size"]}
            valueTexts={[size.toFixed(1)]}
        />
        <span class="w-10 text-end text-label-01 text-text-primary tabular-nums"
            >{size.toFixed(1)}</span
        >
    </div>
{:else if id === "fillErase" || id === "increaseDecrease"}
    {@const [add, cut] =
        id === "fillErase" ? ["Fill", "Erase"] : ["Increase", "Decrease"]}
    <ToggleGroup
        label="{add} or {cut.toLowerCase()}"
        value={workspace.remove ? "remove" : "add"}
        onchange={(value) => {
            workspace.remove = value === "remove";
            done();
        }}
        items={[
            { value: "add", text: add, label: add, tooltip: `${add}  X` },
            { value: "remove", text: cut, label: cut, tooltip: `${cut}  X` },
        ]}
    />
{:else if id === "dilateErode" || id === "questionable"}
    {@const on =
        id === "dilateErode" ? workspace.dilateErode : workspace.questionable}
    <IconButton
        size="icon-xs"
        label={id === "dilateErode" ? "Dilate / Erode" : "Questionable"}
        aria-pressed={on}
        class="aria-pressed:bg-background-selected"
        onclick={() => {
            if (id === "dilateErode") workspace.dilateErode = !on;
            else workspace.questionable = !on;
            done();
        }}
    >
        <!-- Questionable is a filled glyph; Dilate / Erode is an outline. -->
        <span class="size-4 [&>svg]:size-4">
            {#if id === "dilateErode"}<ErodeDilate />{:else}<Questionable
                />{/if}
        </span>
    </IconButton>
{:else if id === "hardness" || id === "pressure"}
    {@const name = id === "hardness" ? "Hardness" : "Pressure"}
    {@const percent = Math.round(workspace.paint[id] * 100)}
    <div class="flex items-center gap-2">
        <span class="text-label-01 text-text-secondary">{name}</span>
        <Slider
            class="w-20"
            values={[percent]}
            min={0}
            max={100}
            onchange={(v) =>
                workspace.setPaint(
                    id === "hardness"
                        ? { hardness: v[0] / 100 }
                        : { pressure: v[0] / 100 },
                )}
            oncommit={done}
            labels={[name]}
            valueTexts={[`${percent}%`]}
        />
        <span class="w-10 text-end text-label-01 text-text-primary tabular-nums"
            >{percent}%</span
        >
    </div>
{:else if id === "undo" || id === "redo"}
    {@const can = id === "undo" ? canUndo : canRedo}
    <!-- aria-disabled, not disabled, so focus stays on the button when the history runs out. -->
    <IconButton
        size="icon-xs"
        label={id === "undo" ? "Undo" : "Redo"}
        shortcut={id === "undo" ? "⌘Z / Ctrl+Z" : "⇧⌘Z / Ctrl+Y"}
        aria-disabled={!can}
        onclick={() => {
            if (!can || !segmentation) return;
            if (id === "undo") segmentation.undo(index);
            else segmentation.redo(index);
            done();
        }}
    >
        {#if id === "undo"}<Undo />{:else}<Redo />{/if}
    </IconButton>
{/if}
