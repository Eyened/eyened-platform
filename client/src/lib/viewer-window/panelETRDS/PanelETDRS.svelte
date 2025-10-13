<script lang="ts">
	import { formAnnotations, createFormAnnotation } from '$lib/data';
	import type { FormSchemaGET } from '../../../types/openapi_types';
	import type { TaskContext } from '$lib/tasks/TaskContext.svelte';
	import {
	    ETDRSGridOverlay,
	    type etdrsFormAnnotationType
	} from '$lib/viewer/overlays/ETDRSGridOverlay.svelte';
	import { ETDRSGridTool } from '$lib/viewer/tools/ETDRSGrid.svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext, onDestroy } from 'svelte';
	import { Hide, Show, PanelIcon } from '../icons/icons';
	import { ViewerWindowContext } from '../viewerWindowContext.svelte';
	import ETDRSGridItem from './ETDRSGridItem.svelte';

	interface Props {
		active: boolean;
		etdrsSchema: FormSchemaGET;
	}
	let { active, etdrsSchema }: Props = $props();

    let firstOpen = true;
	$effect(() => {
		if (!active) {
			tool.annotation = undefined;
		} else {
            if (autoItem && firstOpen) {
                overlay.visible.add(autoItem);
                firstOpen = false;
            }
        }
	});

	const { creator, registration } = getContext<ViewerWindowContext>('viewerWindowContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
	const taskContext = getContext<TaskContext>('taskContext');

	const { image } = viewerContext;
	const { instance } = image;

	const filtered = $derived(
		formAnnotations.filter(formAnnotation => {
			if (formAnnotation.form_schema_id !== etdrsSchema.id) return false;
			
			if (formAnnotation.image_instance_id == image.instance.id) return true;

			// also show annotations on linked images
			// TODO: this should be reactive?
			const linkedIDs = registration.getLinkedImgIds(image.image_id);
			if (linkedIDs.has(`${formAnnotation.image_instance_id}`)) return true;
			if (linkedIDs.has(`${formAnnotation.image_instance_id}_proj`)) return true;
			return false;
		})
	);


	async function create() {
		await createFormAnnotation({
			form_schema_id: etdrsSchema.id,
			patient_id: instance.patient.id,
			study_id: instance.study?.id ?? undefined,
			image_instance_id: instance.id,
			sub_task_id: taskContext?.subTask?.id,
			form_data: {},
		});
	}

	const overlay = new ETDRSGridOverlay(registration);
	const tool = new ETDRSGridTool(image.image_id);
	onDestroy(viewerContext.addOverlay(overlay));
	onDestroy(viewerContext.addOverlay(tool));

	let autoItem: etdrsFormAnnotationType | undefined = $state(undefined);
	if (instance.cf_keypoints) {
		const [fx, fy] = instance.cf_keypoints.fovea_xy as [number, number];
		const [odx, ody] = instance.cf_keypoints.disc_edge_xy as [number, number];
		autoItem = {
			instance: instance as any,
			value: {
				fovea: { x: fx, y: fy },
				disc_edge: { x: odx, y: ody }
			}
		};        
	}
	function toggleVisisble() {
		if (autoItem && overlay.visible.has(autoItem)) {
			overlay.visible.delete(autoItem);
		} else if (autoItem) {
			overlay.visible.add(autoItem);
		}
	}
    let autoToggleIcon = $derived.by(() => {
        if (autoItem && overlay.visible.has(autoItem)) {
            return Show;
        } else {
            return Hide;
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

		{#each filtered as formAnnotation (formAnnotation.id)}
			<ETDRSGridItem {overlay} {tool} formAnnotation={formAnnotation as any} />
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
