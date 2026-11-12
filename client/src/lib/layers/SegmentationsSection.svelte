<!--
@component
Layers › Segmentations for the selected viewport: opacity and Area, the old drawing tools until 3b replaces them, and rows grouped AI, Mine, then other graders.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import DrawingTools from "$lib/viewer-window/panelSegmentation/DrawingTools.svelte";
    import NewSegmentation from "$lib/viewer-window/panelSegmentation/NewSegmentation.svelte";
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
    import Add from "carbon-icons-svelte/lib/Add.svelte";
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
    let newOpen = $state(false);

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
        {#snippet action()}
            <NewSegmentation bind:open={newOpen} />
        {/snippet}
        {#if count > 0}
            <div class="flex items-center gap-3 px-4 py-2">
                <span class="text-label-01 text-text-secondary">Opacity</span>
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
                <Field.Field orientation="horizontal" class="w-auto shrink-0">
                    <Toggle
                        id="{uid}-area"
                        bind:checked={() => showArea, setArea}
                    />
                    <Field.Label
                        for="{uid}-area"
                        class="text-body-compact-01 text-text-primary"
                        >Area</Field.Label
                    >
                </Field.Field>
            </div>
            <!-- The old tools' hidden tooltips stick out past the panel edge and make it scroll sideways. -->
            <div class="overflow-x-clip"><DrawingTools /></div>
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
        {:else}
            <Empty.Root class="px-4 py-6">
                <Empty.Header>
                    <!-- ASSUMPTION: the spec asks for one description line but gives no text. -->
                    <Empty.Title>No segmentations</Empty.Title>
                    <Empty.Description
                        >Create one to draw on this image.</Empty.Description
                    >
                </Empty.Header>
                <Button
                    variant="ghost"
                    size="sm"
                    onclick={() => (newOpen = true)}
                    >New segmentation <Add /></Button
                >
            </Empty.Root>
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
