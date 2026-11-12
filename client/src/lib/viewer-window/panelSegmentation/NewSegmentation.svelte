<!--
@component
New on the Segmentations header: a popover with the feature search, where focus starts, then Advanced… and Region box….
`open` is bindable so the empty state's button opens the same popover.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { features } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import { getContext } from "svelte";
    import type { FeatureGET } from "../../../types/openapi_types";
    import CreateSegmentationDialog from "./CreateSegmentationDialog.svelte";
    import { createQuestionableSegmentation } from "./createSegmentationHelpers";
    import FeatureSelect from "./FeatureSelect.svelte";

    let { open = $bindable(false) }: { open?: boolean } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;
    const { image, axis } = viewerContext;
    let content: HTMLElement | null = $state(null);

    async function createQuestionable(feature: FeatureGET) {
        open = false;
        await createQuestionableSegmentation(
            globalContext,
            segmentationContext,
            image,
            axis,
            feature,
            taskContext?.subTask?.id,
        );
    }

    function openAdvanced() {
        open = false;
        globalContext.dialogue = {
            component: CreateSegmentationDialog,
            props: {
                image,
                axis,
                segmentationContext,
                subtaskId: taskContext?.subTask?.id,
                initialMode: "full",
            },
        };
    }

    function startRegionBox() {
        open = false;
        segmentationContext.pendingRegionBox = undefined;
        segmentationContext.regionToolActive = true;
    }

    // Typing a feature name is the next step, so focus starts in the search.
    function onOpenAutoFocus(e: Event) {
        e.preventDefault();
        content?.querySelector<HTMLInputElement>("input")?.focus();
    }
</script>

<Popover.Root bind:open>
    <Popover.Trigger>
        {#snippet child({ props })}
            <Button
                {...props}
                variant="ghost"
                size="sm"
                aria-label="New segmentation">New <Add /></Button
            >
        {/snippet}
    </Popover.Trigger>
    <Popover.Content
        bind:ref={content}
        align="end"
        {onOpenAutoFocus}
        class="flex flex-col gap-2"
    >
        <FeatureSelect
            label="Search feature to create"
            values={features.map((f) => f)}
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
