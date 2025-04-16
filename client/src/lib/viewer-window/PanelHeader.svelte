<script lang="ts">
	import type { PanelName } from '$lib/viewer/viewer-utils';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext, type Snippet } from 'svelte';
	import MainIcon from './icons/MainIcon.svelte';

	interface Props {
		text: string;
		icon: Snippet;
		panelName: PanelName;
	}
	let { text = '', icon, panelName }: Props = $props();

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { activePanels } = viewerContext;
	let active = $derived(activePanels.has(panelName));

	function toggle() {
		if (activePanels.has(panelName)) {
			activePanels.delete(panelName);
		} else {
			activePanels.add(panelName);
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<h3 class:active onclick={toggle}>
	<span id="chev">
		{#if active}
			&#9660;
		{:else}
			&#9654;
		{/if}
	</span>
	<MainIcon {active} {icon} />
	<span>{text}</span>
</h3>

<style>
	h3 {
		display: flex;
		align-items: center;
		border-bottom: 1px solid rgb(45, 45, 45);
		margin: 0;
	}
	span#chev {
		width: 1em;
	}
	h3:hover {
		cursor: pointer;
		background-color: rgb(45, 45, 45);
	}
	h3.active {
		background-color: rgb(48, 102, 102);
		color: white;
	}
	span {
		margin-left: 0.5em;
	}
</style>
