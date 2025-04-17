<script lang="ts">
	import Viewer from '$lib/viewer/Viewer.svelte';
	import PanelETDRS from './panelETRDS/PanelETDRS.svelte';
	import PanelRegistration from './panelRegistration/PanelRegistration.svelte';

	import { getContext, onDestroy, setContext } from 'svelte';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import Dialogue from './Dialogue.svelte';
	import { get_url_params } from '$lib/utils';
	import PanelRendering from './panelRendering/PanelRendering.svelte';
	import type { AbstractImage } from '$lib/webgl/abstractImage';
	import type { DialogueType, TaskContext } from '$lib/types';
	import PanelMeasure from './panelMeasure/PanelMeasure.svelte';
	import { writable } from 'svelte/store';
	import PanelForm from './panelForm/PanelForm.svelte';
	import PanelLayers from './panelLayers/PanelLayers.svelte';
	import type { ViewerEvent } from '$lib/viewer/viewer-utils';
	import { ViewerWindowContext } from './viewerWindowContext.svelte';
	import MainIcon from './icons/MainIcon.svelte';

	import PanelHeader from './PanelHeader.svelte';
	import { Close, Info, Rendering, ETDRS, Registration, Form, Draw } from './icons/icons';

	import Measure from './icons/Measure.svelte';
	import PanelInfo from './panelInfo/panelInfo.svelte';
	import PanelSegmentation from './panelSegmentation/PanelSegmentation.svelte';
	import Layers from './icons/Layers.svelte';
	import { data } from '$lib/datamodel/model';

	interface Props {
		image: AbstractImage;
	}

	let { image }: Props = $props();

	const taskContext = getContext<TaskContext>('taskContext');

	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	const { registration } = viewerWindowContext;
	const closePanel = getContext<() => {}>('closePanel');

	const viewerContext = new ViewerContext(image, registration);
	setContext('viewerContext', viewerContext);

	const { activePanels } = viewerContext;

	const params = get_url_params();

	if (params['panel']) {
		activePanels.add(params['panel']);
	}

	if (taskContext) {
		// const taskDefinitionName = taskContext.task.definition.name;
		// if (['ETDRS-grid placement', 'Naevi', 'Glaucoma grading'].includes(taskDefinitionName)) {
		// 	activePanels.add('Form');
		// }
		// if (['Consensus segmentation'].includes(taskDefinitionName)) {
		// 	activePanels.add('Segmentation');
		// }
	}
	const dialogue = writable<DialogueType>(undefined);
	setContext('dialogue', dialogue);

	// const miniViewerContext: Writable<ViewerContext | undefined> = writable(undefined);
	// setContext('miniViewerContext', miniViewerContext);

	// zoom in on top viewer for this image
	const topViewer = viewerWindowContext.topViewers.get(image)!;

	const overlay = {
		pointermove(e: ViewerEvent<PointerEvent>) {
			const { viewerContext } = e;
			const { x, y } = e.cursor;
			const { viewerSize } = viewerContext;
			const p = viewerContext.viewerToImageCoordinates({ x, y });
			const scaleH = viewerSize.height / image.height;
			const scaleW = viewerSize.width / image.width;
			const baseFactor = Math.min(scaleH, scaleW);
			// TODO: let user choose factor
			let factor = image.is3D ? 0.4 : 5;
			if (image.image_id.endsWith('_proj')) {
				factor = 0.5;
			}
			topViewer.focusPoint(p.x, p.y, factor * baseFactor);
		},
		pointerleave() {
			topViewer.initTransform();
		}
	};
	onDestroy(viewerContext.addOverlay(overlay));
	onDestroy(() => {
		topViewer.initTransform();
	});

	let minimize = $state(viewerWindowContext.mainPanels.length > 1);

	const { formSchemas } = data;
	const etdrsSchema = formSchemas.find((schema) => schema.name === 'ETDRS-grid coordinates')!;
	if (!etdrsSchema) {
		console.warn('ETDRS schema not found');
	}
	const registrationSchema = formSchemas.find((schema) => schema.name === 'Pointset registration')!;
	if (!registrationSchema) {
		console.warn('Registration schema not found');
	}
</script>

<Dialogue />

<div class="main">
	<div id="viewer">
		<Viewer />
	</div>
	<div id="right">
		<div id="close" class:vertical={minimize}>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<span class="image-id" onclick={() => (minimize = !minimize)} class:minimize>
				&#9660; [{image.image_id}]
			</span>

			<MainIcon onclick={closePanel} tooltip="Close">
				{#snippet icon()}
					<Close />
				{/snippet}
			</MainIcon>

			{#if minimize}
				<MainIcon onclick={() => (minimize = false)} tooltip="Close">
					{#snippet icon()}
						<span class="dots">&#8942;</span>
					{/snippet}
				</MainIcon>
			{/if}
		</div>

		<div id="panels" class:minimize>
			<PanelHeader text="Info" panelName="Info">
				{#snippet icon()}
					<Info />
				{/snippet}
			</PanelHeader>
			<div class="panel {activePanels.has('Info') ? 'expanded' : 'collapsed'}">
				<PanelInfo />
			</div>

			<PanelHeader text="Rendering" panelName="Rendering">
				{#snippet icon()}
					<Rendering />
				{/snippet}
			</PanelHeader>
			<div class="panel {activePanels.has('Rendering') ? 'expanded' : 'collapsed'}">
				<PanelRendering />
			</div>

			{#if image.is2D && etdrsSchema}
				<PanelHeader text="ETDRS" panelName="ETDRS">
					{#snippet icon()}
						<ETDRS />
					{/snippet}
				</PanelHeader>
				<div class="panel {activePanels.has('ETDRS') ? 'expanded' : 'collapsed'}">
					<PanelETDRS {etdrsSchema} active={activePanels.has('ETDRS')} />
				</div>
			{/if}

            {#if image.is2D && registrationSchema}
                <PanelHeader text="Registration" panelName="Registration">
                    {#snippet icon()}
                        <Registration />
                    {/snippet}
                </PanelHeader>
                <div class="panel {activePanels.has('Registration') ? 'expanded' : 'collapsed'}">
                    <PanelRegistration {registrationSchema} active={activePanels.has('Registration')} />
                </div>
            {/if}
			<PanelHeader text="Measure" panelName="Measure">
				{#snippet icon()}
					<Measure />
				{/snippet}
			</PanelHeader>
			<div class="panel {activePanels.has('Measure') ? 'expanded' : 'collapsed'}">
				<PanelMeasure active={activePanels.has('Measure')} />
			</div>

			<PanelHeader text="Form" panelName="Form">
				{#snippet icon()}
					<Form />
				{/snippet}
			</PanelHeader>
			<div class="panel {activePanels.has('Form') ? 'expanded' : 'collapsed'}">
				<PanelForm />
			</div>

			<PanelHeader text="Segmentation" panelName="Segmentation">
				{#snippet icon()}
					<Draw />
				{/snippet}
			</PanelHeader>
			<div class="panel {activePanels.has('Segmentation') ? 'expanded' : 'collapsed'}">
				<PanelSegmentation />
			</div>

			{#if image.is3D}
				<PanelHeader text="Layers" panelName="LayerSegmentation">
					{#snippet icon()}
						<Layers />
					{/snippet}
				</PanelHeader>
				<div class="panel {activePanels.has('LayerSegmentation') ? 'expanded' : 'collapsed'}">
					<PanelLayers />
				</div>
			{/if}
		</div>
		<!-- 
		{#if $activePanels.has('LayerSegmentation')}
			<div class="segmentation-panels">
				<PanelLayerSegmentation {viewerContext} />
			</div>
		{/if}
	 	-->
	</div>
</div>

<style>
	div {
		display: flex;
		flex: 1;
		user-select: none;
		color: rgba(255, 255, 255, 0.8);
	}
	div.vertical {
		flex-direction: column;
	}
	.minimize {
		display: none;
	}
	div.main {
		flex-direction: row;
	}
	div#viewer {
		flex: 1;
	}
	div#panels {
		flex-direction: column;
		flex: 1;

		overflow-y: auto;
		overflow-x: hidden;
		padding-bottom: 4em;
	}
	div#right {
		flex-direction: column;
		flex: 0;
		background-color: black;
		/* border-left: 1px solid rgba(255, 255, 255, 0.4); */
		border-right: 1px solid rgba(255, 255, 255, 0.4);
	}

	div#close,
	div.panel {
		height: auto;
		flex: 0;
	}
	span.image-id {
		display: flex;
		flex: 1;
		cursor: pointer;
		margin: auto;
		font-size: 0.8em;
	}
	span.image-id.minimize {
		display: none;
	}
	.panel.collapsed {
		height: 0;
		overflow: hidden;
	}
	.panel.expanded {
		background-color: rgba(255, 255, 255, 0.1);
		height: auto;
	}
	span.dots {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.2em;
		width: 1.5em;
		height: 1.5em;
		margin: auto;
		/* font-size: large; */
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 50%;
		font-weight: bold;
	}
</style>
