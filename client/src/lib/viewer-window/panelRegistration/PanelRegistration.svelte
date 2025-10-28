<script lang="ts">
	import {
		createFormAnnotation,
		deleteFormAnnotation,
		formAnnotations,
		instances,
	} from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { RegistrationTool } from "$lib/viewer/tools/Registration";
	import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import type { FormSchemaGET } from "../../../types/openapi_types";
	import RegistrationItem from "./RegistrationItem.svelte";
	import { Button } from "$lib/components/ui/button";

	const viewerContext = getContext<ViewerContext>("viewerContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const globalContext = getContext<GlobalContext>("globalContext");

	interface props {
		active: boolean;
		registrationSchema: FormSchemaGET;
	}
	const { active: panelActive, registrationSchema }: props = $props();

	const {
		image: { instance },
	} = viewerContext;

	//filter all registrations for the same eye
	const filtered = $derived(
		formAnnotations
			.filter((formAnnotation) => {
				if (formAnnotation.form_schema_id !== registrationSchema.id)
					return false;
				if (formAnnotation.patient_id !== instance.patient.id) return false;
				// Check laterality - look up full instance if needed
				const formInstance = formAnnotation.image_instance_id
					? instances.get(formAnnotation.image_instance_id)
					: null;
				if (formInstance && formInstance.laterality !== instance.laterality) {
					return false;
				}
				return true;
			})
			.sort((a, b) => a.id - b.id),
	);

	async function create() {
		const formAnnotation = await createFormAnnotation({
			form_schema_id: registrationSchema.id,
			patient_id: instance.patient.id,
			study_id: instance.study?.id ?? undefined,
			image_instance_id: instance.id,
			sub_task_id: taskContext?.subTask?.id,
			form_data: {},
		});
        onactivate(formAnnotation);
	}

	let activeID: number | undefined = $state(undefined);
	let removeTool: (() => void) | undefined = $state(undefined);

	function onactivate(formAnnotation: any) {
		// Check if this annotation still exists in the filtered list
		const stillExists = filtered.some(f => f.id === formAnnotation.id);
		if (!stillExists) {
			console.log("Annotation no longer exists, ignoring onactivate");
			return;
		}

		if (activeID === formAnnotation.id) {
			// deactivate current
			removeTool?.();
			removeTool = undefined;
			activeID = undefined;
			return;
		}
		
		const canEdit = globalContext.canEdit(formAnnotation);
		const tool = new RegistrationTool(
			formAnnotation,
			viewerContext.image.instance as any,
			canEdit,
		);
		activeID = formAnnotation.id;
        // switch to new one
		removeTool?.();     
		removeTool = viewerContext.addOverlay(tool);
	}

	function onremove(formAnnotation: any) {
		if (activeID === formAnnotation.id) {
			removeTool?.();
			removeTool = undefined;
			activeID = undefined;
		}
		deleteFormAnnotation(formAnnotation.id);
	}
	$effect(() => {
		if (!panelActive) {
			activeID = undefined;
			removeTool?.();
			removeTool = undefined;
		}
	});
</script>

<div class="main">
	<div class="available">
		<ul>
			{#each filtered as formAnnotation (formAnnotation.id)}
				<RegistrationItem
					{formAnnotation}
					active={activeID === formAnnotation.id}
					{onactivate}
					{onremove}
				/>
			{/each}
		</ul>
	</div>
	<div class="new">
		<Button variant="outline" onclick={create}>Create new</Button>
	</div>
</div>

<style>
	div.main {
		padding: 0.5em;
		min-height: 0;
		flex: 1 1 auto;
		overflow-y: auto;
		min-height: 0px;
	}
	div.new,
	div.available {
		padding: 0.2em;
		margin-bottom: 0.5em;
	}
	ul {
		list-style-type: none;
		padding-inline-start: 0em;
	}
</style>
