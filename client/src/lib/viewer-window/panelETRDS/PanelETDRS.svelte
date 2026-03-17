<script lang="ts">
	import Button from "$lib/components/ui/button/button.svelte";
	import Input from "$lib/components/ui/input/input.svelte";
	import { createFormAnnotation, formAnnotations } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
	import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
	import { ETDRSGridTool } from "$lib/viewer/tools/ETDRSGrid.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import type {
		FormAnnotationGET,
		FormSchemaGET,
	} from "../../../types/openapi_types";
	import { Hide, PanelIcon, Show } from "../icons/icons";
	import { ViewerWindowContext } from "../viewerWindowContext.svelte";
	import ETDRSGridItem from "./ETDRSGridItem.svelte";
	import { SvelteMap, SvelteSet } from "svelte/reactivity";

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
	const globalContext = getContext<GlobalContext>("globalContext");
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

			if (formAnnotation.image_id == instance.id) return true;

			// also show annotations on linked images
			// TODO: this should be reactive?
			const linkedIDs = registration.getLinkedImgIds(image_id);
			if (linkedIDs.has(`${formAnnotation.image_id}`)) return true;
			if (linkedIDs.has(`${formAnnotation.image_id}_proj`))
				return true;
			return false;
		}),
	);

	let overlayIds = new SvelteSet<number>();
	let toolIds = new SvelteSet<number>();
	let overlays = new SvelteMap<number, () => void>();
	let tools = new SvelteMap<number, () => void>();

	function deactivateAll() {
		removeAutoOverlay?.();
		removeAutoOverlay = undefined;
		for (const remove of overlays.values()) remove();
		for (const remove of tools.values()) remove();
		overlays.clear();
		tools.clear();
		overlayIds.clear();
		toolIds.clear();
	}

	function toggle(
		formAnnotation: FormAnnotationGET,
		activeIds: SvelteSet<number>,
		items: SvelteMap<number, () => void>,
		createItem: () => any,
		active?: boolean,
		precondition?: () => boolean,
	) {
		if (!filtered.some((f) => f.id === formAnnotation.id)) return;
		if (precondition && !precondition()) return;
		const id = formAnnotation.id;
		const isActive = activeIds.has(id);
		const shouldBeActive = active !== undefined ? active : !isActive;

		if (shouldBeActive === isActive) return;

		if (shouldBeActive) {
			activeIds.add(id);
			items.set(id, viewerContext.addOverlay(createItem()));
		} else {
			items.get(id)?.();
			items.delete(id);
			activeIds.delete(id);
		}
	}

	function toggleOverlay(formAnnotation: FormAnnotationGET, active?: boolean) {
		toggle(
			formAnnotation,
			overlayIds,
			overlays,
			() => new ETDRSGridItemOverlay(formAnnotation as any, registration, settings),
			active,
		);
	}

	function toggleTool(formAnnotation: FormAnnotationGET, active?: boolean) {
		toggle(
			formAnnotation,
			toolIds,
			tools,
			() => new ETDRSGridTool(formAnnotation),
			active,
			() => globalContext.canEdit(formAnnotation),
		);
	}

	async function create() {
		deactivateAll();
		const newAnnotation = await createFormAnnotation({
			form_schema_id: etdrsSchema.id,
			patient_id: instance.patient.id,
			study_id: instance.study?.id ?? undefined,
			image_id: instance.id,
			laterality: instance.laterality ?? undefined,
			sub_task_id: taskContext?.subTask?.id,
			form_data: {},
		});
		toggleOverlay(newAnnotation, true);
		toggleTool(newAnnotation, true);
	}

	$effect(() => {
		if (!active) {
			deactivateAll();
		}
	});

	const autoItem: etdrsGridType | undefined = $derived.by(() => {
		if (!instance.cf_keypoints) return undefined;
		const [fx, fy] = instance.cf_keypoints.fovea_xy as [number, number];
		const [odx, ody] = instance.cf_keypoints.disc_edge_xy as [number, number];
		return {
			image_id: String(image_id),
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
			<ETDRSGridItem
				{formAnnotation}
				{settings}
				overlayActive={overlayIds.has(formAnnotation.id)}
				toolActive={toolIds.has(formAnnotation.id)}
				onToggleOverlay={toggleOverlay}
				onToggleTool={toggleTool}
			/>
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
