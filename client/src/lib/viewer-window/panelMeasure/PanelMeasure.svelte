<script lang="ts">
	import { MeasureTool } from '$lib/viewer/tools/Measure.svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext, onDestroy } from 'svelte';
	import { ViewerWindowContext } from '../viewerWindowContext.svelte';
	import MeasureAreas from './MeasureAreas.svelte';
	import { data } from '$lib/datamodel/model';
	import Line from './Line.svelte';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import SetResolutionEtdrs from './SetResolutionETDRS.svelte';
	interface props {
		active: boolean;
	}
	const { active }: props = $props();

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { image } = viewerContext;

	const measureTool = new MeasureTool(image);
	let remove = () => {};
	onDestroy(() => remove());

	$effect(() => {
		if (active) {
			remove = viewerContext.addOverlay(measureTool);
		} else {
			remove();
		}
	});

	// filter any annotation that can be linked to this image using the registration
	const { registration } = getContext<ViewerWindowContext>('viewerWindowContext');
	const { formAnnotations, formSchemas } = data;

	// TODO: code duplicated from PanelETDRS.svelte (refactor?)
	const etdrsSchema = formSchemas.find((schema) => schema.name === 'ETDRS-grid coordinates')!;

	const filter = (formAnnotation: FormAnnotation) => {
		if (formAnnotation.formSchema !== etdrsSchema) return false;
		if (formAnnotation.instance == image.instance) return true;
		// TODO: this should be reactive?
		const linkedIDs = registration.getLinkedImgIds(image.image_id);
		if (linkedIDs.has(`${formAnnotation.instance?.id}`)) return true;
		if (linkedIDs.has(`${formAnnotation.instance?.id}_proj`)) return true;
		return false;
	};
	const filtered = formAnnotations.filter(filter);

	let fraction = $state(0.85);

	const cfKeypoints = image.instance.cfKeypoints;
	const autoValue = cfKeypoints
		? {
				fovea: { x: cfKeypoints.fovea_xy[0], y: cfKeypoints.fovea_xy[1] },
				disc_edge: { x: cfKeypoints.disc_edge_xy[0], y: cfKeypoints.disc_edge_xy[1] }
			}
		: null;

	let hideRes = $state(true);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div id="main">
	<div class="resolution">
		<div>
			{measureTool.imageResX.toFixed(2)} × {measureTool.imageResY.toFixed(2)} μm/pix
		</div>
		<h3 class:hideRes onclick={() => (hideRes = !hideRes)}>
			{#if hideRes}
				&#9658;
			{:else}
				&#9660;
			{/if}
			Image resolution
		</h3>

		<div id="set-resolution" class:hideRes>
			<div>
				<label>
					x:
					<input type="number" bind:value={measureTool.imageResX} step="0.1" /> μm/pix
				</label>
			</div>
			<div>
				<label>
					y:
					<input type="number" bind:value={measureTool.imageResY} step="0.1" /> μm/pix
				</label>
			</div>

			<div class="presets">
				{#if measureTool.dbResAvailable}
					<SetResolutionEtdrs
						valueFixed={image.resolution.x}
						{measureTool}
						name="database"
						{fraction}
					/>
				{/if}

				From ETDRS:
				<div>
					<span
						title="The fraction of the distance between fovea and optic disc edge that wil be assumed to be 3mm"
						>Fraction:</span
					>
					<input type="number" bind:value={fraction} step="0.01" />
				</div>
				{#if autoValue}
					<SetResolutionEtdrs value={autoValue} {measureTool} name="automatic" {fraction} />
				{/if}

				{#each $filtered as formAnnotation (formAnnotation.id)}
					<SetResolutionEtdrs
						value={formAnnotation.value.value}
						{measureTool}
						name={`[${formAnnotation.id}]`}
						{fraction}
					/>
				{/each}
			</div>
		</div>
	</div>
	<div class="segmentation-area">
		<h4>Line distances</h4>
		<ul>
			{#each measureTool.lines as line}
				{#if line.index == viewerContext.index}
					<Line {line} {measureTool} />
				{/if}
			{/each}
		</ul>
	</div>
	<div class="segmentation-area">
		<h4>Segmentation area</h4>
		<MeasureAreas {measureTool} />
	</div>
</div>

<style>
	div {
		display: flex;
	}
	h3 {
		cursor: pointer;
		margin: 0;
		background-color: rgba(255, 255, 255, 0.1);
	}
	h3:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
	div#set-resolution {
		background-color: rgba(255, 255, 255, 0.1);
		padding: 0.5em;
	}
	div.hideRes {
		visibility: hidden;
		max-height: 0;
	}

	input {
		width: 4em;
	}
	div#main,
	div.resolution,
	div#set-resolution {
		flex: 1;
		flex-direction: column;
	}
	div.resolution {
		flex: 1;
		padding: 0.5em;
		flex-direction: column;
	}
	div.presets {
		flex-direction: column;
	}

	ul {
		list-style-type: none;
		padding: 0;
		margin: 0;
	}
	h4 {
		margin: 0;
	}
	div.segmentation-area {
		display: flex;
		flex-direction: column;
		/* margin-left: 1em; */
	}
</style>
