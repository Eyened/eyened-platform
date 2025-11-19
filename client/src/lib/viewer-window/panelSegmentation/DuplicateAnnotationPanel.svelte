<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";
    import { Duplicate } from "../icons/icons";
    import { duplicate, types } from "./duplicate_utils";
    import type { Segmentation } from "./segmentationContext.svelte";
    import { Button } from "$lib/components/ui/button/index.js";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";

    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
    }

    let { segmentation, image, segmentationItem }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");

    let duplicateVolume = $state(false);

    let type = $state<"Q" | "B" | "P">("Q");
    type = Object.keys(types).find(
        (t) => types[t as "Q" | "B" | "P"] == segmentation.data_representation,
    ) as "Q" | "B" | "P";

    function applyDuplicate() {
        duplicate(
            globalContext,
            segmentation,
            segmentationItem,
            image,
            viewerContext,
            duplicateVolume,
            type,
            segmentationItem.threshold ?? segmentation.threshold ?? 0.5, //original threshold
            0.5, //new threshold
            taskContext
        );
    }
</script>

<div class="main">
    <h3><Duplicate size="1.5em" />Duplicate</h3>

    {#if image.is3D}
        <div>
            <label>
                <input type="radio" bind:group={duplicateVolume} value={true} />
                Volume
            </label>
            <label>
                <input
                    type="radio"
                    bind:group={duplicateVolume}
                    value={false}
                />
                B-scan
            </label>
        </div>
    {/if}
    {#if segmentation.data_representation == "MultiClass" || segmentation.data_representation == "MultiLabel"}{:else}
        <div>
            <label>
                <input type="radio" bind:group={type} value="Q" />
                Q
            </label>
            <label>
                <input type="radio" bind:group={type} value="B" />
                B
            </label>
            <label>
                <input type="radio" bind:group={type} value="P" />
                P
            </label>
        </div>
    {/if}
    <Button variant="outline" onclick={applyDuplicate}>Create copy</Button>
</div>

<style>
    div.main {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
        margin-bottom: 0.2em;
        margin-top: 0.2em;
    }
    h3 {
        font-size: small;
        font-weight: bold;
        margin: 0;
        padding: 0;
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
</style>
