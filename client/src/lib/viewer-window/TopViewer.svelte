<script lang="ts">
	import Viewer from '$lib/viewer/Viewer.svelte';
	import { getContext, setContext } from 'svelte';
	import type { ViewerWindowContext } from './viewerWindowContext.svelte';
	import type { AbstractImage } from '$lib/webgl/abstractImage';
	import MainIcon from './icons/MainIcon.svelte';
	import { OCTLinesOverlay } from '$lib/viewer/overlays/OCTLinesOverlays';
	import Lines from './icons/Lines.svelte';

	interface Props {
		image: AbstractImage;
	}

	let { image }: Props = $props();

	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');

	const viewerContext = viewerWindowContext.topViewers.get(image)!;
	setContext('viewerContext', viewerContext);

	// const registration = viewerContext.registration;
	// let linkedImages = $derived(registration.getLinkedImgIds(image.image_id));

	let photoLocators = $derived(viewerWindowContext.photoLocators.get(image.image_id)!);
	let hasLocators = $derived(image.is2D && photoLocators && photoLocators.length);
	let removeOverlay = () => {};
	let hideOverlay = $state(false);

	$effect(() => {
		removeOverlay();
		if (hasLocators && !hideOverlay) {
			removeOverlay = viewerContext.addOverlay(new OCTLinesOverlay(photoLocators));
		} else {
			removeOverlay();
		}
		return removeOverlay;
	});
	function toggleOverlay(e: MouseEvent) {
		e.stopPropagation();
		hideOverlay = !hideOverlay;
	}

	function selectImage(e: any) {
		if (e.shiftKey) {
			viewerWindowContext.addImagePanel(image);
		} else {
			viewerWindowContext.setImagePanel(image);
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="item" class:wide={image.is3D} onclick={(e) => selectImage(e)}>
	<Viewer showInfo={false} />
	{#if hasLocators}
		<div class="header overlay">
			<div class="content outer">
				<div class="content">
					<MainIcon onclick={toggleOverlay} active={!hideOverlay}>
						{#snippet icon()}
							<Lines />
						{/snippet}
					</MainIcon>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	div {
		flex: 1;
		display: flex;
	}
	div.overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		pointer-events: none;
	}
	div.content {
		pointer-events: auto;
		flex: 0;
	}
	div.content.outer {
		flex-direction: column;
	}
	div.item {
		border-bottom: 1px solid gray;
		z-index: 2;
		border-right: 1px solid gray;
		position: relative;
	}
	div.item:hover {
		border-bottom: 1px solid white;
	}
	div.wide {
		flex: 2;
	}
	div.header {
		color: white;
		display: flex;
		margin: 0.5em;
	}
</style>
