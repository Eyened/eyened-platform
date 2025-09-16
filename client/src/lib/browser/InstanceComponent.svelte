<script lang="ts">
    import { getThumbUrl } from "$lib/data-loading/utils";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";
    import type { components } from "../../types/openapi";
    import type { BrowserContext } from "./browserContext.svelte";
    import InstanceInfo from "./InstanceInfo.svelte";
    type Instance = components['schemas']['InstanceGET'];

    const browserContext = getContext<BrowserContext>("browserContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const { user: creator } = globalContext;

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
    let popupOpen = $state(false)

    // const segmentations = instance.segmentations;
    // const creatorCounts = segmentations.reduce(
    //     (acc, seg) => {
    //         acc[seg.creator.name] = (acc[seg.creator.name] || 0) + 1;
    //         return acc;
    //     },
    //     {} as { [name: string]: number },
    // );

    

    const image_url = getThumbUrl(instance)!;

    const selected = $derived(browserContext.selection.includes(instance.id));

    function toggleSelect() {
        browserContext.toggleInstance(instance);
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="main flex flex-col rounded-[0.1em] p-[0.2em] border-[0.2em] border-transparent"
    class:border-[#72de80]={selected}
    class:outline={showPatientInfo}
    class:outline-1={showPatientInfo}
    class:outline-[#d0d0d0]={showPatientInfo}
    class:m-[0.2em]={showPatientInfo}
>
    <div class="title text-sm flex flex-col text-gray-500 cursor-pointer hover:text-black" onclick={()=>{popupOpen=true}}>
        {#if showPatientInfo}
            <div class="flex justify-center flex-1">
                {instance.patient.identifier}
            </div>
            <div class="flex justify-center flex-1">
                {instance.study.date}
            </div>
        {/if}
        <div>
            {instance.id}
        </div>
    </div>
    <div class="tile flex flex-col flex-1 items-center" onclick={toggleSelect}>
        {#if image_url}
            <div
                class="img bg-black m-px cursor-pointer flex flex-col items-center [flex-flow:column-reverse] bg-contain bg-no-repeat bg-center"
                style:width={size}
                style:height={size}
                style:background-image="url('{image_url}')"
            >
                {#if instance.dicom_modality == "OPT"}
                    <div class="oct-info text-[10px] text-white/70">
                        [{instance.anatomic_region}] ({instance.nr_of_frames} x {instance.columns})
                    </div>
                {/if}
            </div>

            <!-- {#if showSegmentationInfo && $segmentations.length}
                <ul>
                    {#each Object.entries($creatorCounts) as [c, count]}
                        <li class:has-own-segmentations={creator.name == c}>
                            {count} x {c}
                        </li>
                    {/each}
                </ul>
            {/if} -->
        {/if}
    </div>
    <InstanceInfo {instance} open={popupOpen}/>
</div>

<style>

</style>
