<!--
@component
New on the Segmentations header: a popover with the Feature combo box, where focus starts, then Advanced… and Region box….
`open` is bindable so the empty state's button opens the same popover.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { ComboBox } from "$lib/components/ui/combo-box/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { features } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import { getContext } from "svelte";
    import { createQuestionableSegmentation } from "./createSegmentationHelpers";

    let { open = $bindable(false) }: { open?: boolean } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;
    const { image, axis } = viewerContext;
    let content: HTMLElement | null = $state(null);
    let trigger: HTMLElement | null = $state(null);

    let text = $state("");
    const items = $derived.by(() => {
        const q = text.trim().toLowerCase();
        return features
            .filter((f) => f.name.toLowerCase().includes(q))
            .map((f) => ({ id: String(f.id), text: f.name }));
    });

    // While it saves, the header shows "Creating…" in New's place; the section moves focus back to New after.
    async function createQuestionable(id: string) {
        const feature = features.get(Number(id));
        if (!feature) return;
        open = false;
        segmentationContext.failed = null;
        segmentationContext.busy = "Creating…";
        try {
            await createQuestionableSegmentation(
                globalContext,
                segmentationContext,
                image,
                axis,
                feature,
                taskContext?.subTask?.id,
            );
        } catch {
            segmentationContext.failed = "Couldn't create the segmentation";
        } finally {
            segmentationContext.busy = null;
        }
    }

    function openAdvanced() {
        open = false;
        segmentationContext.createDialog = {};
    }

    function startRegionBox() {
        open = false;
        segmentationContext.regionToolActive = true;
    }

    // Typing a feature name is the next step, so focus starts in the combo box.
    function onOpenAutoFocus(e: Event) {
        const input = content?.querySelector<HTMLInputElement>("input");
        if (!input) return;
        e.preventDefault();
        input.focus();
    }

    // The empty state's button can open this popover and then unmount, so focus always goes to the header button.
    function onCloseAutoFocus(e: Event) {
        e.preventDefault();
        trigger?.focus();
    }
</script>

<Popover.Root bind:open>
    <Popover.Trigger bind:ref={trigger}>
        {#snippet child({ props })}
            <IconButton {...props} size="icon-xs" label="New segmentation"
                ><Add /></IconButton
            >
        {/snippet}
    </Popover.Trigger>
    <Popover.Content
        bind:ref={content}
        align="end"
        {onOpenAutoFocus}
        {onCloseAutoFocus}
        class="flex flex-col gap-2"
    >
        <ComboBox
            titleText="Feature"
            {items}
            bind:value={text}
            onselect={createQuestionable}
        />
        <Button
            variant="ghost"
            size="sm"
            class="justify-start"
            onclick={openAdvanced}>Advanced…</Button
        >
        <Button
            variant="ghost"
            size="sm"
            class="justify-start"
            onclick={startRegionBox}>Region box…</Button
        >
    </Popover.Content>
</Popover.Root>
