<!--
@component
Layers › En-face projection for the selected viewport: one Off / Mask / Thickness switcher per OCT this image is or links to, each with a line naming the viewport its content comes from.
-->
<script lang="ts">
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import type { EnfaceOverlaySourceResolved } from "$lib/registration/resolveEnfaceOverlaySources";
    import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import {
        getEnfaceFeatureIndices,
        isProjectable,
    } from "$lib/viewer-window/enfaceProjectionKeys";
    import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { getContext } from "svelte";
    import LayerSection from "./LayerSection.svelte";
    import { octLabel } from "./octLabel";

    let {
        sources,
        open,
        ontoggle,
    }: {
        sources: EnfaceOverlaySourceResolved[];
        open: boolean;
        ontoggle: () => void;
    } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const uid = $props.id();

    const MODES = [
        { value: "off", text: "Off", label: "Off" },
        { value: "binary", text: "Mask", label: "Mask" },
        { value: "heatmap", text: "Thickness", label: "Thickness" },
    ];

    function setMode(source: EnfaceOverlaySourceResolved, mode: string) {
        if (source.identityMapping)
            viewerContext.enfaceProjectionMode = mode as EnfaceProjectionMode;
        else
            viewerContext.setEnfaceProjectionModeForOct(
                source.octPublicId,
                mode as EnfaceProjectionMode,
            );
    }

    function helper(source: EnfaceOverlaySourceResolved): string {
        const from = source.manager.source;
        if (!from)
            return "Not open in a viewport. Drag its tile into one to project it.";
        const ctx = from.mainViewerContext.segmentationContext;
        // In Thickness a MultiClass segmentation paints only the one active class, so with several active, or one it lacks, it paints nothing.
        const paintsNothing = (s: Segmentation) =>
            source.mode === "heatmap" &&
            s.data_representation === "MultiClass" &&
            (typeof ctx.activeIndices !== "number" ||
                !getEnfaceFeatureIndices(s).includes(ctx.activeIndices));
        const n = [
            ...ctx.visibleGraderSegmentations,
            ...ctx.visibleModelSegmentations,
        ].filter((s) => isProjectable(s) && !paintsNothing(s)).length;
        const where = `From viewport ${from.position() + 1}`;
        if (n === 0) return `${where}: no segmentations shown`;
        const opacity = Math.round(from.mainViewerContext.alpha * 100);
        return `${where}: ${n} segmentation${n === 1 ? "" : "s"}, opacity ${opacity} %`;
    }
</script>

<LayerSection title="En-face projection" {open} {ontoggle}>
    <ul>
        {#each sources as source, i (source.octPublicId)}
            {@const label = octLabel(
                source.octPublicId,
                source.manager.octImage.depth,
            )}
            <li class="flex flex-col gap-1 py-2 ps-8 pe-4">
                <span class="text-body-compact-01 text-text-primary"
                    >{label}</span
                >
                <ToggleGroup
                    label="En-face projection, {label}"
                    describedby="{uid}-{i}"
                    value={source.mode}
                    onchange={(mode) => setMode(source, mode)}
                    items={MODES}
                    class="self-start"
                />
                <p id="{uid}-{i}" class="text-helper-text-01 text-text-helper">
                    {helper(source)}
                </p>
            </li>
        {/each}
    </ul>
</LayerSection>
