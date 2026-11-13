<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { RadioButtonGroup } from "$lib/components/ui/radio-button/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";
    import { duplicate, types } from "./duplicate_utils";
    import type { Segmentation } from "./segmentationContext.svelte";

    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
        /** Called before the copy starts, so the popover holding this panel can close. */
        oncreate?: () => void;
    }

    let { segmentation, image, segmentationItem, oncreate }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const uid = $props.id();

    type Letter = "Q" | "B" | "P";
    const representation = $derived(segmentation.data_representation);
    const isMulti = $derived(
        representation === "MultiClass" || representation === "MultiLabel",
    );

    let copy = $state<"slice" | "volume">("slice");
    // The row's own type; MultiClass and MultiLabel copies keep theirs, so the letter is unused there.
    let type = $state<Letter>(
        (Object.keys(types) as Letter[]).find(
            (t) => types[t] === segmentation.data_representation,
        ) ?? "Q",
    );

    function applyDuplicate() {
        oncreate?.();
        duplicate(
            globalContext,
            segmentation,
            segmentationItem,
            image,
            viewerContext,
            copy === "volume",
            type,
            segmentationItem.threshold ?? segmentation.threshold ?? 0.5, // original threshold
            0.5, // new threshold
            taskContext,
        );
    }
</script>

<section class="flex flex-col gap-3" aria-labelledby="{uid}-heading">
    <h5 id="{uid}-heading" class="text-heading-compact-01 text-text-primary">
        Duplicate
    </h5>
    {#if image.is3D}
        <RadioButtonGroup
            legendText="Copy"
            items={[
                { value: "slice", labelText: "This B-scan" },
                { value: "volume", labelText: "Volume" },
            ]}
            bind:selected={copy}
        />
    {/if}
    {#if isMulti}
        <p class="text-body-compact-01 text-text-secondary">
            Keeps the {representation} type.
        </p>
    {:else}
        <RadioButtonGroup
            legendText="Type"
            items={[
                { value: "Q", labelText: "Questionable (Q)" },
                { value: "B", labelText: "Binary (B)" },
                { value: "P", labelText: "Probability (P)" },
            ]}
            bind:selected={type}
        />
    {/if}
    <Button
        variant="outline"
        size="sm"
        class="self-start"
        onclick={applyDuplicate}>Create copy</Button
    >
</section>
