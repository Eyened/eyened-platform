<!--
@component
The classes of a current MultiClass or MultiLabel row: eye, colour and number, the class you draw (MultiClass) or the labels (MultiLabel), the name, and this slice's area while Area is on.
MultiClass rows also get the viewport's two class opacity sliders, which are not saved.
-->
<script lang="ts">
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { RadioButton } from "$lib/components/ui/radio-button/index.js";
    import { SliderField } from "$lib/components/ui/slider/index.js";
    import { classPixelCounts } from "$lib/layers/classArea";
    import { colors } from "$lib/viewer/overlays/colors";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import { type Segmentation } from "./segmentationContext.svelte";
    import { isDrawableSubfeatureIndex } from "./subfeatureBits";

    interface Props {
        segmentation: Segmentation;
        active: boolean;
        /** The Area switch in the section header. */
        showArea: boolean;
    }
    let { segmentation, active, showArea }: Props = $props();

    const { feature, data_representation } = segmentation;
    const uid = $props.id();

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { segmentationContext } = mainViewerContext;
    const { resolution } = viewerContext.image;
    const hasResolution = resolution.x > 0 && resolution.y > 0;

    const isMultiClass = data_representation === "MultiClass";
    // Must not run inside $derived: getOrCreateSegmentationItem mutates the image cache.
    const segmentationItem =
        segmentationContext.getSegmentationItem(segmentation);

    let activeClassIndex = $state(1);
    let activeLabelIndices = $state<number[]>([]);

    const drawableSubfeatures = $derived(
        (feature.subfeatures ?? []).filter((subfeature) =>
            isDrawableSubfeatureIndex(subfeature.index),
        ),
    );

    /** mm² per class this slice; undefined while Area is off, the row is not current or the image has no resolution. */
    const areas = $derived.by(() => {
        if (!active || !showArea || !hasResolution) return undefined;
        const mask = segmentationItem.getMask(viewerContext.index) as
            | { version?: number; exportData(): ArrayLike<number> }
            | undefined;
        if (!mask) return undefined;
        void mask.version; // reruns after every draw, undo or import
        const counts = classPixelCounts(
            mask.exportData(),
            data_representation === "MultiLabel",
            drawableSubfeatures.map((s) => s.index),
        );
        const mm2 = (resolution.x * resolution.y) / 1e6;
        return new Map([...counts].map(([i, n]) => [i, n * mm2]));
    });

    function indicesEqual(a: number | number[], b: number | number[]): boolean {
        if (Array.isArray(a) && Array.isArray(b)) {
            return a.length === b.length && a.every((v, i) => v === b[i]);
        }
        if (!Array.isArray(a) && !Array.isArray(b)) {
            return a === b;
        }
        if (!Array.isArray(a) && Array.isArray(b) && b.length === 1) {
            return a === b[0];
        }
        if (Array.isArray(a) && a.length === 1 && !Array.isArray(b)) {
            return a[0] === b;
        }
        return false;
    }

    $effect(() => {
        if (active) {
            segmentationContext.activeIndices = isMultiClass
                ? activeClassIndex
                : activeLabelIndices;
        }
    });

    $effect(() => {
        if (!active) return;
        const fromCtx = segmentationContext.activeIndices;
        if (isMultiClass) {
            if (typeof fromCtx === "number" && fromCtx !== activeClassIndex) {
                activeClassIndex = fromCtx;
            }
            return;
        }
        if (
            Array.isArray(fromCtx) &&
            !indicesEqual(activeLabelIndices, fromCtx)
        ) {
            activeLabelIndices = fromCtx;
        }
    });

    function toggleLabel(index: number, on: boolean) {
        activeLabelIndices = on
            ? [...activeLabelIndices, index].sort((a, b) => a - b)
            : activeLabelIndices.filter((i) => i !== index);
    }

    function pointerEnter(featureIndex: number) {
        mainViewerContext.highlightedFeatureIndex = featureIndex;
        mainViewerContext.highlightedSegmentationItem = segmentationItem;
    }
    function pointerLeave() {
        mainViewerContext.highlightedFeatureIndex = undefined;
    }

    function toggleLayerVisibility(featureIndex: number) {
        segmentationContext.toggleFeatureLayerVisibility(
            segmentation,
            featureIndex,
        );
        viewerContext.repaint();
    }
</script>

{#if active}
    <div class="flex w-full flex-col gap-3">
        {#if isMultiClass}
            <fieldset class="flex flex-col gap-3">
                <legend class="mb-2 text-label-01 text-text-secondary"
                    >Class opacity</legend
                >
                <!-- Shown as percent; stored as 0 to 1. -->
                <SliderField
                    labelText="Active class"
                    value={segmentationContext.multiClassActiveAlpha * 100}
                    onchange={(v) =>
                        (segmentationContext.multiClassActiveAlpha = v / 100)}
                    min={0}
                    max={100}
                    step={5}
                    decimals={0}
                    unit="%"
                />
                <SliderField
                    labelText="Other classes"
                    value={segmentationContext.multiClassInactiveAlpha * 100}
                    onchange={(v) =>
                        (segmentationContext.multiClassInactiveAlpha = v / 100)}
                    min={0}
                    max={100}
                    step={5}
                    decimals={0}
                    unit="%"
                />
            </fieldset>
        {/if}
        <fieldset class="min-w-0">
            <!-- While areas show, the legend is the visible caption row; otherwise only screen readers get it. -->
            <legend
                class={areas
                    ? "mb-1 flex w-full justify-between text-label-01 text-text-secondary"
                    : "sr-only"}
                ><span>Class</span>{#if areas}<span aria-hidden="true"
                        >Area this slice</span
                    >{/if}</legend
            >
            <ul class="flex flex-col gap-1">
                {#each drawableSubfeatures as subfeature (subfeature.index)}
                    {@const shown = segmentationContext.isFeatureLayerVisible(
                        segmentation,
                        subfeature.index,
                    )}
                    <li
                        class="flex items-start gap-1"
                        onpointerenter={() => pointerEnter(subfeature.index)}
                        onpointerleave={pointerLeave}
                    >
                        <IconButton
                            size="icon-xs"
                            label="{shown ? 'Hide' : 'Show'} {subfeature.name}"
                            onclick={() =>
                                toggleLayerVisibility(subfeature.index)}
                        >
                            {#if shown}<View />{:else}<ViewOff />{/if}
                        </IconButton>
                        <span
                            class="mt-0.5 flex size-5 shrink-0 items-center justify-center text-label-01 text-text-inverse tabular-nums"
                            style="background-color: rgb({colors[
                                subfeature.index - 1
                            ]});"
                            aria-hidden="true">{subfeature.index}</span
                        >
                        {#if isMultiClass}
                            <RadioButton
                                class="min-w-0 flex-1 [overflow-wrap:anywhere]"
                                name="{uid}-class"
                                value={String(subfeature.index)}
                                labelText={subfeature.name}
                                checked={activeClassIndex === subfeature.index}
                                onchange={() =>
                                    (activeClassIndex = subfeature.index)}
                            />
                        {:else}
                            <Checkbox
                                id="{uid}-label-{subfeature.index}"
                                class="mt-1"
                                checked={activeLabelIndices.includes(
                                    subfeature.index,
                                )}
                                onCheckedChange={(on) =>
                                    toggleLabel(subfeature.index, on === true)}
                            />
                            <label
                                for="{uid}-label-{subfeature.index}"
                                class="min-w-0 flex-1 pt-0.5 text-body-compact-01 [overflow-wrap:anywhere] text-text-primary"
                                >{subfeature.name}</label
                            >
                        {/if}
                        {#if areas}
                            <span
                                class="shrink-0 pt-0.5 text-label-01 text-text-primary tabular-nums"
                                ><span class="sr-only">Area this slice </span>{(
                                    areas.get(subfeature.index) ?? 0
                                ).toFixed(2)} mm²</span
                            >
                        {/if}
                    </li>
                {/each}
            </ul>
        </fieldset>
    </div>
{/if}
