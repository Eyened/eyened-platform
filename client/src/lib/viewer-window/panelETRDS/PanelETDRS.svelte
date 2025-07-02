<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { data } from '$lib/datamodel/model';
	import { ViewerWindowContext } from '../viewerWindowContext.svelte';
	import {
		ETDRSGridOverlay,
		type etdrsFormAnnotationType
	} from '$lib/viewer/overlays/ETDRSGridOverlay.svelte';
	import { ETDRSGridTool } from '$lib/viewer/tools/ETDRSGrid.svelte';
	import ETDRSGridItem from './ETDRSGridItem.svelte';
	import { FormAnnotation } from '$lib/datamodel/formAnnotation.svelte';
	import type { TaskContext } from '$lib/types';
	import { Hide, PanelIcon, Show } from '../icons/icons';
	import type { FormSchema } from '$lib/datamodel/formSchema.svelte';

	interface Props {
		active: boolean;
		etdrsSchema: FormSchema;
	}
	let { active, etdrsSchema }: Props = $props();

	$effect(() => {
		if (!active) {
			tool.annotation = undefined;
		}
	});

	const { creator, registration } = getContext<ViewerWindowContext>('viewerWindowContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
	const taskContext = getContext<TaskContext>('taskContext');

	const { formAnnotations } = data;
	const { image } = viewerContext;
	const { instance } = image;

	const filter = (formAnnotation: FormAnnotation) => {
		if (formAnnotation.formSchemaId !== etdrsSchema.id) return false;
        console.log(formAnnotation.formSchemaId, etdrsSchema.id);
        console.log(formAnnotation.instanceId, image.instance.id);
		if (formAnnotation.instanceId == image.instance.id) return true;

		// also show annotations on linked images
		// TODO: this should be reactive?
		const linkedIDs = registration.getLinkedImgIds(image.image_id);
		if (linkedIDs.has(`${formAnnotation.instance?.id}`)) return true;
		if (linkedIDs.has(`${formAnnotation.instance?.id}_proj`)) return true;
		return false;
	};
	const filtered = formAnnotations.filter(filter);


	async function create() {
        await FormAnnotation.createFrom(creator, instance, etdrsSchema, taskContext?.subTask);
	}

	const overlay = new ETDRSGridOverlay(registration);
	const tool = new ETDRSGridTool(image.image_id);
	onDestroy(viewerContext.addOverlay(overlay));
	onDestroy(viewerContext.addOverlay(tool));

	let autoItem: etdrsFormAnnotationType;
	if (instance.cfKeypoints) {
		const [fx, fy] = instance.cfKeypoints.fovea_xy;
		const [odx, ody] = instance.cfKeypoints.disc_edge_xy;
		autoItem = {
			instance,
			value: { value: { fovea: { x: fx, y: fy }, disc_edge: { x: odx, y: ody } } }
		};
		// overlay.visible.add(autoItem);
	}
	function toggleVisisble() {
		if (overlay.visible.has(autoItem)) {
			overlay.visible.delete(autoItem);
		} else {
			overlay.visible.add(autoItem);
		}
	}
    let autoToggleIcon = $derived.by(() => {
        if (overlay.visible.has(autoItem)) {
            return Hide;
        } else {
            return Show;
        }
    });
</script>

<div class="main">
	<div class="etdrs-fraction">
		<label for="etdrsRadiusFraction">ETDRS radius fraction:</label>
		<input
			type="number"
			id="etdrsRadiusFraction"
			bind:value={overlay.radiusFraction}
			step="0.01"
			min="0.01"
			max="1"
		/>
	</div>
	<div class="available">
		{#if autoItem}
			<div class="automatic">
				<PanelIcon
					active={overlay.visible.has(autoItem)}
					onclick={toggleVisisble}
					tooltip="show/hide"
                    Icon={autoToggleIcon}
				/>
				Automatic
			</div>
		{/if}

		{#each $filtered as formAnnotation (formAnnotation.id)}
            {#await formAnnotation.load()}
                <div>Loading [{formAnnotation.id}]§</div>
            {:then}
                <ETDRSGridItem {overlay} {tool} {formAnnotation} />
            {/await}
		{/each}
	</div>
	<div class="new">
		<button onclick={create}> Create new ETDRS grid annotation </button>
	</div>
</div>

<style>
	div.main {
		padding: 0.5em;
	}

	input {
		width: 5em;
	}
	div.automatic {
		display: flex;
		background-color: rgba(255, 255, 255, 0.1);
		align-items: center;
		border: 1px solid black;
		border-radius: 2px;
		padding: 0.2em;
	}
	div.automatic:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
</style>
