<script lang="ts">
	import Button from "$lib/components/ui/button/button.svelte";
	import Input from "$lib/components/ui/input/input.svelte";
	import { createFormAnnotation, formAnnotations } from "$lib/data";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
	import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import type { FormSchemaGET } from "../../../types/openapi_types";
	import { Hide, PanelIcon, Show } from "../icons/icons";
	import { ViewerWindowContext } from "../viewerWindowContext.svelte";
	import ETDRSGridItem from "./ETDRSGridItem.svelte";

	interface Props {
		active: boolean;
		etdrsSchema: FormSchemaGET;
	}
	let { active, etdrsSchema }: Props = $props();

	const viewerWindowContext = getContext<ViewerWindowContext>(
		"viewerWindowContext",
	);

	const viewerContext = getContext<ViewerContext>("viewerContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const registration = viewerWindowContext.registration;

	const image = viewerContext.image;
	const instance = image.instance;
	const image_id = image.image_id;
	let settings = $state({
		radiusFraction: 0.85,
	});
	const filtered = $derived(
		formAnnotations.filter((formAnnotation) => {
			if (formAnnotation.form_schema_id !== etdrsSchema.id) return false;

			if (formAnnotation.image_instance_id == instance.id) return true;

			// also show annotations on linked images
			// TODO: this should be reactive?
			const linkedIDs = registration.getLinkedImgIds(image_id);
			if (linkedIDs.has(`${formAnnotation.image_instance_id}`)) return true;
			if (linkedIDs.has(`${formAnnotation.image_instance_id}_proj`))
				return true;
			return false;
		}),
	);

	async function create() {
		await createFormAnnotation({
			form_schema_id: etdrsSchema.id,
			patient_id: instance.patient.id,
			study_id: instance.study?.id ?? undefined,
			image_instance_id: instance.id,
			laterality: instance.laterality ?? undefined,
			sub_task_id: taskContext?.subTask?.id,
			form_data: {},
		});
	}

	const autoItem: etdrsGridType | undefined = $derived.by(() => {
		if (!instance.cf_keypoints) return undefined;
		const [fx, fy] = instance.cf_keypoints.fovea_xy as [number, number];
		const [odx, ody] = instance.cf_keypoints.disc_edge_xy as [number, number];
		return {
			image_instance_id: String(image_id),
			form_data: {
				fovea: { x: fx, y: fy },
				disc_edge: { x: odx, y: ody },
			},
		};
	});

	// Manage an overlay instance for the auto item
	let removeAutoOverlay: (() => void) | undefined = $state(undefined);
	function toggleVisisble() {
		if (!autoItem) return;
		if (removeAutoOverlay) {
			removeAutoOverlay();
			removeAutoOverlay = undefined;
		} else {
			const itemOverlay = new ETDRSGridItemOverlay(
				autoItem,
				registration,
				settings,
			);
			removeAutoOverlay = viewerContext.addOverlay(itemOverlay);
		}
	}
	let showHide = $derived(removeAutoOverlay ? Show : Hide);
</script>

<div class="main">
	<div class="etdrs-fraction">
		<label for="etdrsRadiusFraction">ETDRS radius fraction:</label>
		<Input
			type="number"
			id="etdrsRadiusFraction"
			bind:value={settings.radiusFraction}
			step="0.01"
			min="0.01"
			max="1"
		/>
	</div>
	<div class="available">
		{#if autoItem}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="automatic">
				<PanelIcon
					active={removeAutoOverlay != undefined}
					onclick={toggleVisisble}
					tooltip="show/hide"
					Icon={showHide}
				/>

				Automatic
			</div>
		{/if}

		{#each filtered as formAnnotation (formAnnotation.id)}
			<ETDRSGridItem {formAnnotation} {settings} />
		{/each}
	</div>
	<div class="new">
		<Button onclick={create}>Create new</Button>
	</div>
</div>

<style>
	div.main {
		padding: 0.5em;
		flex: 1;
	}
	div.etdrs-fraction {
		display: flex;
		align-items: center;
		gap: 0.5em;
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
