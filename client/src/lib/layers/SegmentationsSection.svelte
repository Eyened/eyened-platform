<!--
@component
Layers › Segmentations for the selected viewport: opacity and Area, the old drawing tools until 3b replaces them, and rows grouped AI, Mine, then other graders.
-->
<script lang="ts">
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import DrawingTools from "$lib/viewer-window/panelSegmentation/DrawingTools.svelte";
    import NewSegmentationRegion from "$lib/viewer-window/panelSegmentation/NewSegmentationRegion.svelte";
    import SegmentationItem from "$lib/viewer-window/panelSegmentation/SegmentationItem.svelte";
    import {
        getSegmentationKey,
        type Segmentation,
    } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { groupByCreator } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
    import {
        readLayerArea,
        writeLayerArea,
    } from "$lib/workspace/workspacePrefs";
    import { getContext } from "svelte";
    import LayerSection from "./LayerSection.svelte";
    import SegmentationDeleteModal from "./SegmentationDeleteModal.svelte";

    let {
        open,
        ontoggle,
        shown,
    }: {
        open: boolean;
        ontoggle: () => void;
        /** True while Layers is on screen. */
        shown: boolean;
    } = $props();

    const uid = $props.id();
    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const { segmentationContext } = mainViewerContext;
    const me = globalContext.user.id;

    type Group = { key: string; title: string; rows: Segmentation[] };
    const groups: Group[] = $derived.by(() => {
        const byCreator = groupByCreator(
            segmentationContext.graderSegmentations,
        );
        const result: Group[] = [];
        if (segmentationContext.modelSegmentations.length > 0)
            result.push({
                key: "ai",
                title: "AI",
                rows: segmentationContext.modelSegmentations,
            });
        const mine = byCreator.get(me);
        if (mine) result.push({ key: String(me), title: "Mine", rows: mine });
        for (const [creatorId, rows] of byCreator)
            if (creatorId !== me)
                result.push({
                    key: String(creatorId),
                    title: rows[0].creator.name,
                    rows,
                });
        return result;
    });
    const count = $derived(groups.reduce((n, g) => n + g.rows.length, 0));

    let showArea = $state(readLayerArea());
    function setArea(on: boolean) {
        showArea = on;
        writeLayerArea(on);
    }
    const percent = $derived(Math.round(mainViewerContext.alpha * 100));

    // The old drawing tools and the pipette act only while this section is on screen.
    $effect(() => {
        if (!shown || !open) return;
        viewerContext.activePanels.add("Segmentation");
        return () => viewerContext.activePanels.delete("Segmentation");
    });

    let deleting: Segmentation | null = $state(null);
    let deleteOpen = $state(false);
    let header: HTMLElement | undefined = $state();
    function askDelete(segmentation: Segmentation) {
        deleting = segmentation;
        deleteOpen = true;
    }
</script>

<div bind:this={header}>
    <LayerSection title="Segmentations" {count} {open} {ontoggle}>
        {#if count > 0}
            <div class="flex items-center gap-3 px-4 py-2">
                <span
                    id="{uid}-opacity"
                    class="text-label-01 text-text-secondary">Opacity</span
                >
                <Slider
                    class="min-w-0 flex-1"
                    values={[percent]}
                    onchange={(v) => (mainViewerContext.alpha = v[0] / 100)}
                    oncommit={() => mainViewerContext.saveOpacity()}
                    min={0}
                    max={100}
                    labels={["Opacity"]}
                    valueTexts={[`${percent}%`]}
                />
                <span class="w-10 text-end text-label-01 text-text-primary"
                    >{percent}%</span
                >
                <Checkbox
                    id="{uid}-area"
                    bind:checked={() => showArea, setArea}
                />
                <label
                    for="{uid}-area"
                    class="text-body-compact-01 text-text-primary">Area</label
                >
            </div>
            <DrawingTools />
            {#each groups as group (group.key)}
                <LayerSection
                    level={4}
                    title={group.title}
                    count={group.rows.length}
                    open={segmentationContext.isGroupOpen(group.key, me)}
                    ontoggle={() =>
                        segmentationContext.toggleGroup(group.key, me)}
                >
                    <ul>
                        {#each group.rows as segmentation (getSegmentationKey(segmentation))}
                            <li>
                                <SegmentationItem
                                    {segmentation}
                                    {showArea}
                                    ondelete={askDelete}
                                />
                            </li>
                        {/each}
                    </ul>
                </LayerSection>
            {/each}
        {/if}
    </LayerSection>
</div>
<NewSegmentationRegion />
<SegmentationDeleteModal
    segmentation={deleting}
    {segmentationContext}
    bind:open={deleteOpen}
    onfallback={() => header?.querySelector<HTMLElement>("button")?.focus()}
/>
