<script lang="ts">
    import { getThumbUrl } from "$lib/data-loading/utils";
    import { getContext, onDestroy } from "svelte";
    import type { Instance } from "$lib/datamodel/instance.svelte";
    import InstanceInfo from "./InstanceInfo.svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import { openNewWindow } from "$lib/newWindow";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const { creator } = globalContext;

    interface Props {
        instance: Instance;
        showPatientInfo?: boolean;
        showSegmentationInfo?: boolean;
    }

    let {
        instance,
        showPatientInfo = false,
        showSegmentationInfo = false,
    }: Props = $props();

    let size = $derived(browserContext.thumbnailSize + "em");

    const segmentations = instance.annotations;
    const creatorCounts = segmentations.reduce(
        (acc, seg) => {
            acc[seg.creator.name] = (acc[seg.creator.name] || 0) + 1;
            return acc;
        },
        {} as { [name: string]: number },
    );

    const image_url = getThumbUrl(instance)!;

    const selected = $derived(browserContext.selection.includes(instance.id));

    function toggleSelect() {
        browserContext.toggleInstance(instance);
    }
    let window: Window | null = null;
    function selectInstance() {
        const props = { instance };
        window = openNewWindow(
            InstanceInfo,
            props,
            `Image info: [${instance.id}]`,
        );
    }
    onDestroy(() => {
        if (window) {
            window.close();
        }
    });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" class:selected class:showPatientInfo>
    <div class="title" onclick={selectInstance}>
        {#if showPatientInfo}
            <div>
                {instance.patient.identifier}
            </div>
            <div>
                {instance.study.date.toISOString().slice(0, 10)}
            </div>
        {/if}
        <div>
            {instance.id}
        </div>
    </div>
    <div class="tile" onclick={toggleSelect}>
        {#if image_url}
            <div
                class="img"
                style:width={size}
                style:height={size}
                style:background-image="url('{image_url}')"
            >
                {#if instance.dicomModality == "OPT"}
                    <div class="oct-info">
                        [{instance.anatomicRegion}] ({instance.nrOfFrames} x {instance.columns})
                    </div>
                {/if}
            </div>

            {#if showSegmentationInfo && $segmentations.length}
                <ul>
                    {#each Object.entries($creatorCounts) as [c, count]}
                        <li class:has-own-segmentations={creator.name == c}>
                            {count} x {c}
                        </li>
                    {/each}
                </ul>
            {/if}
        {/if}
    </div>
</div>

<style>
    div {
        display: flex;
    }
    ul {
        list-style-type: none;
        padding: 0;
        margin: 0;
        font-size: x-small;
    }
    li {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 10em;
    }
    div.title {
        font-size: small;
        flex-direction: column;
        color: gray;
        cursor: pointer;
        display: flex;
    }
    div.title > div {
        flex: 1;
        justify-content: center;
    }

    div.oct-info {
        font-size: x-small;
        color: rgba(255, 255, 255, 0.7);
    }
    div.title:hover {
        color: black;
    }
    div.img {
        background-color: black;
        margin: 1px;
        cursor: pointer;
        flex-direction: column;
        align-items: center;
        flex-flow: column-reverse;

        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }
    div.main {
        flex-direction: column;
        border-radius: 0.1em;
        padding: 0.2em;
        border: 0.2em solid transparent;
    }
    div.main.selected {
        border: 0.2em solid #72de80;
    }
    div.main.showPatientInfo {
        outline: 1px solid #d0d0d0;
        margin: 0.2em;
    }
    div.tile {
        flex-direction: column;
        flex: 1;
        align-items: center;
    }
    div.tile:hover {
        transition:
            transform 0.3s ease,
            box-shadow 0.3s ease;
        box-shadow: 0 5px 10px rgba(0, 0, 0, 0.1);
        cursor: pointer;
    }

    .has-own-segmentations {
        background-color: #acdde1;
    }
</style>
