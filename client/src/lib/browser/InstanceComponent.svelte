<script lang="ts">
	import * as Dialog from "$lib/components/ui/dialog";
	import { getThumbUrl } from "$lib/data-loading/utils";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { getContext } from "svelte";
import type { ImageGET } from "../../types/openapi_types";
	import type { BrowserContext } from "./browserContext.svelte";
	import InstanceInfoLazy from "./InstanceInfoLazy.svelte";

	const browserContext = getContext<BrowserContext>("browserContext");
	const globalContext = getContext<GlobalContext>("globalContext");

	interface Props {
		instance: ImageGET;
		showSegmentationInfo?: boolean;
	}

	let { instance, showSegmentationInfo = false }: Props = $props();
	let size = $derived(browserContext.thumbnailSize);
	let popupOpen = $state(false);

	// const segmentations = instance.segmentations;
	// const creatorCounts = segmentations.reduce(
	//     (acc, seg) => {
	//         acc[seg.creator.name] = (acc[seg.creator.name] || 0) + 1;
	//         return acc;
	//     },
	//     {} as { [name: string]: number },
	// );

	const image_url = $derived(getThumbUrl(instance));

	const selected = $derived(browserContext.selectedIds.includes(instance!.id));

	function toggleSelect() {
		browserContext.toggleInstance(instance);
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="main flex flex-col rounded-[0.1em] p-[0.2em] border-[0.2em] border-transparent"
	class:bg-emerald-50={selected}
	class:ring-2={selected}
	class:ring-emerald-400={selected}
>
	<div
		class="title text-sm flex flex-col text-gray-500 cursor-pointer hover:text-black items-center"
		onclick={() => {
			popupOpen = true;
		}}
	>
		<div>
			{instance.id}
		</div>
	</div>
	<div
		class="tile flex flex-col flex-1 items-center justify-center"
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
		<!-- {#if instance.dicom_modality == "OPT"}
                    <div class="oct-info text-[10px] text-white/70">
                        [{instance.anatomic_region}] ({instance.nr_of_frames} x {instance.columns})
                    </div>
                {/if}
            </div> -->

		<!-- {#if showSegmentationInfo && $segmentations.length}
                <ul>
                    {#each Object.entries($creatorCounts) as [c, count]}
                        <li class:has-own-segmentations={creator.name == c}>
                            {count} x {c}
                        </li>
                    {/each}
                </ul>
            {/if} -->
	</div>

	<Dialog.Root bind:open={popupOpen}>
		<Dialog.Content class="sm:max-w-[85vw] max-h-[85vh]">
			<InstanceInfoLazy instanceId={instance.id} />
		</Dialog.Content>
	</Dialog.Root>
</div>

<style>
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
