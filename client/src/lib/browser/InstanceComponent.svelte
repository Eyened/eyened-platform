<script lang="ts">
    import * as Dialog from "$lib/components/ui/dialog";
    import CopyIconButton from "$lib/components/CopyIconButton.svelte";
    import { getThumbUrl } from "$lib/data-loading/utils";

    import { getContext } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import type { BrowserContext } from "./browserContext.svelte";
    import InstanceInfoLazy from "./InstanceInfoLazy.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");

    interface Props {
        instance: ImageGET;
        showSegmentationInfo?: boolean;
    }

    let { instance, showSegmentationInfo = false }: Props = $props();
    let size = $derived(browserContext.thumbnailSize);
    let popupOpen = $state(false);

    const image_url = $derived(getThumbUrl(instance));

    const selected = $derived(
        browserContext.selectedIds.includes(instance!.id),
    );

    function toggleSelect() {
        browserContext.toggleInstance(instance);
    }
    const name_map = {
        AdaptiveOptics: "AO",
        ColorFundus: "CFI",
        ColorFundusStereo: "CF Stereo",
        RedFreeFundus: "Red Free",
        ExternalEye: "External",
        LensPhotograph: "Lens",
        Ophthalmoscope: "OS",
        Autofluorescence: "AF",
        FluoresceinAngiography: "FA",
        ICGA: "ICGA",
        InfraredReflectance: "IR",
        BlueReflectance: "BR",
        GreenReflectance: "GR",
        OCT: "OCT",
        OCTA: "OCTA",
    };

    let name = "";
    if (instance.modality && name_map[instance.modality]) {
        name += name_map[instance.modality];
    }
    if (instance.etdrs_field) {
        name += ` ${instance.etdrs_field}`;
    }
    if (instance.modality == "OCT") {
        name += ` [${instance.nr_of_frames}]`;
    }

    const publicId = $derived(instance.id);

    function openInfoPanel() {
        popupOpen = true;
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="main flex flex-col rounded-[0.1em] border-[0.2em] border-transparent p-[0.2em]"
    class:bg-emerald-50={selected}
    class:ring-2={selected}
    class:ring-emerald-400={selected}
>
    <div
        class="title group cursor-pointer text-sm text-gray-500 hover:text-black"
        onclick={openInfoPanel}
    >
        <div class="title-flip">
            <div class="title-face title-face-default text-xs">{name}</div>
            <div class="title-face title-face-hover text-xs">
                <span class="public-id truncate">{publicId}</span>
                <CopyIconButton
                    text={publicId}
                    ariaLabel="Copy public ID"
                    class="shrink-0"
                />
            </div>
        </div>
    </div>
    <div
        class="tile flex flex-1 flex-col items-center justify-center"
        onpointerdown={toggleSelect}
    >
        <div class="thumbnail-container" style="width: {size}; height: {size};">
            {#if image_url}
                <img
                    src={image_url}
                    alt="Thumbnail"
                    loading="lazy"
                    class="thumbnail"
                    draggable="false"
                />
            {/if}
        </div>
    </div>

    <Dialog.Root bind:open={popupOpen}>
        <Dialog.Content class="max-h-[85vh] sm:max-w-[85vw]">
            <InstanceInfoLazy instanceId={instance.id} />
        </Dialog.Content>
    </Dialog.Root>
</div>

<style>
    .title {
        width: 100%;
        min-height: 1.25rem;
    }

    .title-flip {
        position: relative;
        width: 100%;
        min-height: 1.25rem;
        transform-style: preserve-3d;
        transition: transform 0.2s ease;
    }

    .group:hover .title-flip {
        transform: rotateX(180deg);
    }

    .title-face {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: 1.25rem;
        backface-visibility: hidden;
    }

    .title-face-hover {
        position: absolute;
        inset: 0;
        gap: 0.15rem;
        padding-inline: 0.1rem;
        transform: rotateX(180deg) translateZ(1px);
        pointer-events: none;
    }

    .group:hover .title-face-default {
        pointer-events: none;
    }

    .group:hover .title-face-hover {
        pointer-events: auto;
    }

    .public-id {
        min-width: 0;
    }

    .thumbnail-container {
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: black;
    }

    img.thumbnail {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
</style>
