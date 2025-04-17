<!--
@component
Some UI components on the top right of the viewer window.
-->
<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { ViewerWindowContext } from './viewerWindowContext.svelte';
	import MainIcon from './icons/MainIcon.svelte';
	import MultiImageViewer from './MultiImageViewer.svelte';
	import { data } from '$lib/datamodel/model';
	import { Image2D } from '$lib/webgl/image2D';
	import { GlobalContext } from '$lib/data-loading/globalContext.svelte';
	import UserMenu from '$lib/UserMenu.svelte';

	const globalContext = getContext<GlobalContext>('globalContext');
	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	const { creator } = viewerWindowContext;
	const { instances } = data;

	let firstCFIImage: undefined | Image2D = $state(undefined);
	onMount(async () => {
		const instance = instances.find((i) => i.modality === 'ColorFundus');
		if (instance) {
			firstCFIImage = (await viewerWindowContext.getImages(instance.id))[0] as Image2D;
		}
	});

	const initials = creator.name
		.split(' ')
		.map((name) => name[0])
		.join('');

	function showUserMenu() {
		globalContext.popupComponent = { component: UserMenu };
	}
	function browse() {
		viewerWindowContext.browserOverlay = true;
	}
	function addMultiImageRendering() {
		const panel = {
			component: MultiImageViewer,
			props: { image: firstCFIImage }
		};
		viewerWindowContext.addPanel(panel);
	}
</script>

<div id="main">
	<MainIcon onclick={showUserMenu} tooltip={creator.name}>
		{#snippet icon()}
			<span class="icon">{initials}</span>
		{/snippet}
	</MainIcon>
	<MainIcon onclick={browse} tooltip="Browse">
		{#snippet icon()}
			<span class="icon">+</span>
		{/snippet}
	</MainIcon>
	<!-- 
	{#if firstCFIImage}
		<MainIcon onclick={addMultiImageRendering} tooltip={'?'}>
			{#snippet icon()}
				<span class="icon">?</span>
			{/snippet}
		</MainIcon>
	{/if} -->
</div>

<style>
	div {
		display: flex;
	}
	div#main {
		flex-direction: column;
		align-items: center;
		padding: 0.2em;
	}
	span.icon {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.2em;
		width: 2em;
		height: 2em;
		margin: auto;
		/* font-size: large; */
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 50%;
		font-weight: bold;
	}
</style>
