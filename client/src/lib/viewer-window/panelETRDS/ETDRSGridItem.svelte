<script lang="ts">
	import type { ETDRSCoordinates, Position2D } from '$lib/types';
	import { globalContext } from '$lib/main';
	import ShowHideToggle from '../icons/ShowHideToggle.svelte';
	import { Edit, PanelIcon, Trash } from '../icons/icons';
	import type { ETDRSGridOverlay } from '$lib/viewer/overlays/ETDRSGridOverlay.svelte';
	import type { ETDRSGridTool } from '$lib/viewer/tools/ETDRSGrid.svelte';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import type { ServerProperty } from '$lib/datamodel/serverProperty.svelte';
	import { data } from '$lib/datamodel/model';

	

	interface Props {
		overlay: ETDRSGridOverlay;
		tool: ETDRSGridTool;
		formAnnotation: FormAnnotation;
	}
	let { overlay, tool, formAnnotation }: Props = $props();

	const item: ServerProperty<ETDRSCoordinates | undefined> = formAnnotation.value;

	let show = $derived(overlay.visible.has(formAnnotation));
	let active = $derived(tool.annotation?.id == formAnnotation.id);

	const canEditForm = $globalContext.canEdit(formAnnotation);

	function toggleVisisble() {
		if (overlay.visible.has(formAnnotation)) {
			overlay.visible.delete(formAnnotation);
		} else {
			overlay.visible.add(formAnnotation);
		}
	}

	function edit() {
		if (tool.annotation?.id == formAnnotation.id) {
			tool.annotation = undefined;
		} else {
			overlay.visible.add(formAnnotation);
			tool.annotation = formAnnotation;
		}
	}

	function remove() {
		overlay.visible.delete(formAnnotation);
		if (tool.annotation?.id == formAnnotation.id) {
			tool.annotation = undefined;
		}
		data.formAnnotations.delete(formAnnotation);
	}
</script>

{#snippet coordinate(property: Position2D)}
	<span>
		[{Math.round(property.x)}, {Math.round(property.y)}]
	</span>
{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="info">
	<span class="annotation-id">[{formAnnotation.id}]</span>
	<div class="top">
		<PanelIcon active={show} onclick={toggleVisisble} tooltip="show/hide">
			<ShowHideToggle {show} />
		</PanelIcon>
		{#if canEditForm}
			<PanelIcon {active} onclick={edit} tooltip="edit">
				<Edit />
			</PanelIcon>
		{/if}
		{#if canEditForm}
			<div class="spacer"></div>
			<PanelIcon onclick={remove} tooltip="delete">
				<Trash />
			</PanelIcon>
		{/if}
	</div>
	<ul>
		<li>
			{#if $item && $item.fovea}
				<span>Fovea:</span>
				{@render coordinate($item.fovea)}
			{/if}
		</li>
		<li>
			{#if $item && $item.disc_edge}
				<span>Disc edge:</span>
				{@render coordinate($item.disc_edge)}
			{/if}
		</li>
	</ul>
</div>

<style>
	.info {
		display: flex;
		background-color: rgba(255, 255, 255, 0.1);
		flex-direction: column;
		border: 1px solid black;
		border-radius: 2px;
		padding: 0.2em;
	}
	.info:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
	div.top {
		display: flex;
	}
	span.annotation-id {
		font-size: x-small;
	}
	div.spacer {
		flex: 1;
	}
	ul {
		list-style-type: none;
		padding: 0;
		margin: 0;
		font-size: small;
	}
	li {
		display: flex;
		align-items: center;
	}
	li * {
		flex: 1;
	}
</style>
