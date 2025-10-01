<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { getContext } from "svelte";
    import CreatorSegmentations from "./CreatorSegmentations.svelte";
    import DrawingTools from "./DrawingTools.svelte";
    import ModelSegmentations from "./ModelSegmentations.svelte";
    import NewSegmentation from "./NewSegmentation.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        active: boolean;
    }
    let { active }: Props = $props();

    const { user: creator } = globalContext;

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    // This is used to not render when the panel is collapsed
    // Perhaps there is a cleaner solution?
    $effect(() => {
        mainViewerContext.active = active;
    });

    const segmentationContext = mainViewerContext.segmentationContext;



</script>

<div class="main">
    <div class="models">
        <ul class="users">
            {#each segmentationContext.models.values() as model}
                <li>
                    <ModelSegmentations {model} />
                </li>
            {/each}
        </ul>
    </div>
    <DrawingTools />
    <div class="opacity">
        <label>
            Opacity:
            <input
                type="range"
                bind:value={mainViewerContext.alpha}
                min="0"
                max="1"
                step="0.01"
            />
        </label>
    </div>

    <ul class="users">
        {#if segmentationContext.creators.has(creator.id)}
            <li>
                <CreatorSegmentations creator={segmentationContext.creators.get(creator.id)!} />
            </li>
        {/if}
        {#each segmentationContext.creators.values() as creator_}
            {#if creator_.id != creator.id}
                <li>
                    <CreatorSegmentations creator={creator_} />
                </li>
            {/if}
        {/each}
    </ul>
    <NewSegmentation />
</div>

<style>
    div {
        display: flex;
    }
    div.models {
        flex: 1;
        flex-direction: column;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        padding-bottom: 0.5em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
        margin: 0;
    }
    div.opacity {
        padding: 0.5em;
    }
    div.main {
        flex: 1;
        flex-direction: column;
    }
    label {
        display: flex;
    }
</style>
