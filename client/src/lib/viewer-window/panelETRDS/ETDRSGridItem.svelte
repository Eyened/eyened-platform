<script lang="ts">
	import { deleteFormAnnotation } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { Position2D } from "$lib/types";
	import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
	import { ETDRSGridTool } from "$lib/viewer/tools/ETDRSGrid.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext, onDestroy } from "svelte";
	import type { FormAnnotationGET } from "../../../types/openapi_types";
	import { Edit, Hide, PanelIcon, Show, Trash } from "../icons/icons";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerContext = getContext<ViewerContext>("viewerContext");

	interface Props {
		formAnnotation: FormAnnotationGET;
		settings: { radiusFraction: number };
	}
	let { formAnnotation, settings }: Props = $props();

	const tool = new ETDRSGridTool(formAnnotation);
	const fovea: Position2D | undefined = $derived(
		formAnnotation.form_data?.fovea as Position2D | undefined,
	);
	const disc_edge: Position2D | undefined = $derived(
		formAnnotation.form_data?.disc_edge as Position2D | undefined,
	);

	const overlay = new ETDRSGridItemOverlay(
		formAnnotation,
		viewerContext.registration,
		settings,
	);
	// No effect needed; overlay reads latest values via getters during repaint
	let removeTool: (() => void) | undefined = $state(undefined);
	let removeOverlay: (() => void) | undefined = $state(undefined);
	onDestroy(() => removeTool?.());
	onDestroy(() => removeOverlay?.());
	const toolActive = $derived(removeTool != undefined);
	const overlayActive = $derived(removeOverlay != undefined);

	const canEditForm = globalContext.canEdit(formAnnotation);

	function toggleOverlay() {
		if (removeOverlay) {
			removeOverlay();
			removeOverlay = undefined;
		} else {
			removeOverlay = viewerContext.addOverlay(overlay);
		}
	}

	function toggleTool() {
		if (removeTool) {
			removeTool();
			removeTool = undefined;
		} else {
			removeTool = viewerContext.addOverlay(tool);
		}
	}

	function remove() {
		removeOverlay?.();
		removeOverlay = undefined;
		removeTool?.();
		removeTool = undefined;
		deleteFormAnnotation(formAnnotation.id);
	}

	let showHide = $derived(overlayActive ? Show : Hide);
</script>

{#snippet coordinate(label: string, property: Position2D)}
	<li>
		<span>{label}:</span>
		<span>
			[{Math.round(property.x)}, {Math.round(property.y)}]
		</span>
	</li>
{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="info">
	<span class="annotation-id">[{formAnnotation.id}]</span>
	<div class="top">
		<PanelIcon
			active={overlayActive}
			onclick={toggleOverlay}
			tooltip="show/hide"
			Icon={showHide}
		/>

		{#if canEditForm}
			<PanelIcon
				active={toolActive}
				onclick={toggleTool}
				tooltip="edit"
				Icon={Edit}
			/>
		{/if}
		{#if canEditForm}
			<div class="spacer"></div>
			<PanelIcon onclick={remove} tooltip="delete" Icon={Trash} />
		{/if}
	</div>
	<ul>
		{#if fovea}
			{@render coordinate("fovea", fovea)}
		{/if}
		{#if disc_edge}
			{@render coordinate("disc_edge", disc_edge)}
		{/if}
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
