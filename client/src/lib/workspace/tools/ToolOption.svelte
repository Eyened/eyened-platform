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
        | "redo"
        | "scale"
        | "circleSize"
        | "etdrsSlot"
        | "keepGridSize"
        | "radiusFraction"
        | "delete"
        | "pointStep";
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import CommitNumberInput from "$lib/layers/CommitNumberInput.svelte";
    import ScalePopover from "$lib/layers/ScalePopover.svelte";
    import {
        CIRCLE_SIZES,
        type CircleSize,
    } from "$lib/viewer/overlays/etdrsCircles";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import Redo from "carbon-icons-svelte/lib/Redo.svelte";
    import Undo from "carbon-icons-svelte/lib/Undo.svelte";
    import ZoomIn from "carbon-icons-svelte/lib/ZoomIn.svelte";
    import ZoomOut from "carbon-icons-svelte/lib/ZoomOut.svelte";
    import { getContext } from "svelte";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { SIZE_MAX, SIZE_MIN, sizeKey } from "../paint";
    import type { ViewportHandle, Workspace } from "../workspace.svelte";

    let { id, viewport }: { id: OptionId; viewport: ViewportHandle | null } =
        $props();
    const uid = $props.id();

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
    // An armed form point field steps its own points.
    const stepper = $derived(
        pointArming.session ? layers?.formPointTool : layers?.pointTool,
    );
    const image = $derived(layers?.viewerContext.image);
    const size = $derived(image ? workspace.paint[sizeKey(image)] : null);
    const index = $derived(layers?.viewerContext.index ?? 0);
    const segmentation = $derived(
        layers?.mainViewerContext.segmentationContext,
    );
    const canUndo = $derived(segmentation?.canUndo(index) ?? false);
    const canRedo = $derived(segmentation?.canRedo(index) ?? false);

    // The bar's Delete: the selected distance line, Place ETDRS's slot point, or P's current point.
    const remove = $derived.by(() => {
        if (workspace.armedTool === "distance") {
            const distance = layers?.distance;
            const line = layers?.selection.line();
            // Only a line on the shown B-scan, so Delete never removes one the grader can't see.
            return distance &&
                line &&
                line.index === layers?.viewerContext.index
                ? () => distance.remove(line)
                : null;
        }
        const points =
            workspace.armedTool === "etdrs"
                ? layers?.etdrsTool
                : layers?.pointTool;
        return points?.hasCurrent ? () => points.deleteCurrent() : null;
    });

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
{:else if id === "dilateErode" || id === "questionable" || id === "keepGridSize"}
    {@const name =
        id === "dilateErode"
            ? "Dilate / Erode"
            : id === "questionable"
              ? "Questionable"
              : "Keep grid size"}
    {@const on =
        id === "dilateErode"
            ? workspace.dilateErode
            : id === "questionable"
              ? workspace.questionable
              : workspace.keepGridSize}
    <div class="flex items-center gap-2">
        <Checkbox
            id="{uid}-{id}"
            checked={on}
            onCheckedChange={(next) => {
                const value = next === true;
                if (id === "dilateErode") workspace.dilateErode = value;
                else if (id === "questionable") workspace.questionable = value;
                else workspace.keepGridSize = value;
                done();
            }}
        />
        <label for="{uid}-{id}" class="text-body-compact-01 text-text-primary"
            >{name}</label
        >
    </div>
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
{:else if id === "scale" && layers}
    <ScalePopover
        {layers}
        empty={workspace.armedTool === "circle"
            ? "No scale"
            : "No scale · lengths in px"}
    />
{:else if id === "circleSize"}
    <ToggleGroup
        label="ETDRS circle size"
        value={workspace.circleSize}
        onchange={(value) => {
            workspace.circleSize = value as CircleSize;
            done();
        }}
        items={CIRCLE_SIZES.map((size) => ({
            value: size,
            text: size,
            label: size,
            tooltip: `${size}  [ ]`,
        }))}
    />
{:else if id === "etdrsSlot"}
    <ToggleGroup
        label="Point to place"
        value={String(workspace.etdrsSlot)}
        onchange={(value) => {
            workspace.etdrsSlot = value === "1" ? 1 : 0;
            done();
        }}
        items={[
            { value: "0", text: "Fovea", label: "Fovea", tooltip: "Fovea  [" },
            {
                value: "1",
                text: "Disc edge",
                label: "Disc edge",
                tooltip: "Disc edge  ]",
            },
        ]}
    />
{:else if id === "radiusFraction"}
    <!-- One fraction for the viewer: fovea to disc edge × fraction = 3 mm. -->
    <div class="flex items-center gap-2">
        <span class="text-label-01 text-text-secondary" aria-hidden="true"
            >Radius fraction</span
        >
        <CommitNumberInput
            labelText="Radius fraction"
            hideLabel
            size="sm"
            value={workspace.etdrsFraction}
            step={0.01}
            min={0.01}
            max={1}
            oncommit={(v) => (workspace.etdrsFraction = v)}
        />
    </div>
{:else if id === "delete"}
    <!-- aria-disabled, not disabled, so focus stays on the button once nothing is left to delete. -->
    <Button
        variant="ghost"
        size="sm"
        aria-disabled={!remove}
        onclick={() => {
            if (!remove) return;
            remove();
            done();
        }}>Delete</Button
    >
{:else if id === "pointStep" && stepper && layers}
    {@const points = stepper}
    {@const viewer = layers.viewerContext}
    <div role="group" aria-label="Points" class="flex items-center gap-1">
        <IconButton
            size="icon-xs"
            label="Previous point"
            shortcut="["
            onclick={() => {
                points.step(-1, viewer);
                done();
            }}
        >
            <ChevronLeft />
        </IconButton>
        <span class="text-body-compact-01 text-text-primary tabular-nums"
            >Point {points.current === undefined ? "–" : points.current + 1} / {points
                .points.length}</span
        >
        <IconButton
            size="icon-xs"
            label="Next point"
            shortcut="]"
            onclick={() => {
                points.step(1, viewer);
                done();
            }}
        >
            <ChevronRight />
        </IconButton>
    </div>
{/if}
