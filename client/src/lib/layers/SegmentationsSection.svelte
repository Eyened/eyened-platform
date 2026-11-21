<!--
@component
Layers › Segmentations for the selected viewport: opacity and Area, and rows grouped AI, Mine, then other graders.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import NewSegmentation from "$lib/viewer-window/panelSegmentation/NewSegmentation.svelte";
    import NewSegmentationRegion from "$lib/viewer-window/panelSegmentation/NewSegmentationRegion.svelte";
    import CreateSegmentationDialog from "$lib/viewer-window/panelSegmentation/CreateSegmentationDialog.svelte";
    import SegmentationItem from "$lib/viewer-window/panelSegmentation/SegmentationItem.svelte";
    import {
        getSegmentationKey,
        type Segmentation,
    } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { groupByCreator } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import { getContext, untrack } from "svelte";
    import { focusAfterDelete } from "./focusAfterDelete";
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

    const workspace = getContext<Workspace>("workspace");
    const percent = $derived(Math.round(mainViewerContext.alpha * 100));

    // The pipette acts while the Layers tab is on screen, even with this section collapsed.
    $effect(() => {
        if (!shown) return;
        viewerContext.activePanels.add("Segmentation");
        return () => viewerContext.activePanels.delete("Segmentation");
    });

    let deleting: Segmentation | null = $state(null);
    let deleteOpen = $state(false);
    let header: HTMLElement | undefined = $state();

    // Looked up each time: New unmounts while a create or duplicate saves.
    function focusNew() {
        header
            ?.querySelector<HTMLElement>('[aria-label="New segmentation"]')
            ?.focus();
    }

    // If New took focus with it when it unmounted, focus goes back to it once the save ends.
    let wasBusy = false;
    $effect(() => {
        const busy = segmentationContext.busy !== null;
        if (wasBusy && !busy && document.activeElement === document.body)
            focusNew();
        wasBusy = busy;
    });

    // The notice is in the body, so a collapsed section opens to show it; collapsing again is up to the user.
    $effect(() => {
        if (segmentationContext.failed) untrack(() => !open && ontoggle());
    });
    let fallback = () => {};
    function askDelete(segmentation: Segmentation, event: MouseEvent) {
        fallback = focusAfterDelete(
            (event.currentTarget as Element).closest("[data-layer-row]"),
            header ?? null,
        );
        deleting = segmentation;
        deleteOpen = true;
    }
</script>

<div bind:this={header} data-layer-section="segmentations">
    <LayerSection title="Segmentations" {count} {open} {ontoggle}>
        {#snippet action()}
            <!-- Stays mounted so the progress text is announced. -->
            <div role="status">
                {#if segmentationContext.busy}
                    <InlineLoading
                        class="w-auto"
                        status="active"
                        description={segmentationContext.busy}
                    />
                {:else}
                    <NewSegmentation bind:open={newOpen} />
                {/if}
            </div>
        {/snippet}
        {#if segmentationContext.failed}
            <div class="px-4 py-2">
                <InlineNotification
                    title={segmentationContext.failed}
                    subtitle="Try again."
                    role="status"
                />
            </div>
        {/if}
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
            </div>
            <div class="px-4 pb-2">
                <Field.Field orientation="horizontal" class="w-auto">
                    <Toggle
                        id="{uid}-area"
                        bind:checked={
                            () => workspace.layerArea,
                            (on) => workspace.setLayerArea(on)
                        }
                    />
                    <Field.Label
                        for="{uid}-area"
                        class="text-body-compact-01 text-text-primary"
                        >Area</Field.Label
                    >
                </Field.Field>
            </div>
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
                                    showArea={workspace.layerArea}
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
                    disabled={segmentationContext.busy !== null}
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
    onfallback={() => fallback()}
/>
{#if segmentationContext.createDialog}
    {#key segmentationContext.createDialog}
        <CreateSegmentationDialog onfocusnew={focusNew} />
    {/key}
{/if}
