<script lang="ts">
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	// import type { FormAnnotationObject } from "$lib/data/objects.svelte";
	// import type { FormAnnotationsRepo } from "$lib/data/repos.svelte";
	import { createFormAnnotation, deleteFormAnnotation, fetchInstance } from "$lib/data";
	import {
		formSchemas
	} from "$lib/data/stores.svelte";
	import { openNewWindow } from "$lib/newWindow";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { getContext } from "svelte";
	import type { FormAnnotationGET } from "../../../types/openapi_types";
	import Duplicate from "../icons/Duplicate.svelte";
	import { PanelIcon, Trash } from "../icons/icons";
	import FormItemContent from "./FormItemContent.svelte";
	
	const taskContext = getContext<TaskContext>("taskContext");
	const globalContext = getContext<GlobalContext>("globalContext");

	interface Props {
		form: FormAnnotationGET;
		theme?: "light" | "dark";
	}

	let { form, theme = "dark" }: Props = $props();
	
	
	const formSchema = $derived(formSchemas.get(form.form_schema_id)!);
	
	// Compute permissions and schema/date display from form.$
	const canEditForm = globalContext.canEdit(form);

	const date = form.date_inserted ?? "";

	let removing: ReturnType<typeof setInterval> | undefined = $state();
	let progress = $state(0);
	let maxTime = 3000; // 3 seconds

	function deleteAnnotation() {
		progress = 0;
		removing = setInterval(() => {
			progress += 10;
			if (progress >= maxTime) {
				clearInterval(removing);
				removing = undefined;
				deleteFormAnnotation(form.id);
			}
		}, 10);
	}

	async function duplicate() {
		await createFormAnnotation({
			form_schema_id: form.form_schema_id,
			patient_id: form.patient_id,
			study_id: form.study_id ?? undefined,
			image_instance_id: form.image_instance_id!,
			sub_task_id: taskContext?.subTask?.id ?? form.sub_task_id ?? undefined,
			form_data: form.form_data,
			form_annotation_reference_id: form.id,
		});
	}

	let window: Window | null = null;
	async function openInNewWindow(form: FormAnnotationGET) {
		if (window) {
			window.close();
		}
        // need to load the full instance to get the patient, study, etc.
		await fetchInstance(form.image_instance_id!);

		const props = {
			formId: form.id,
			canEdit: canEditForm,
		};

		window = openNewWindow(
			// @ts-expect-error - openNewWindow has loose typing for component props
			FormItemContent,
			props,
			`${formSchema.name} ${form.id}`,
		);
	}

	function formatDateTime(dateString: string) {
		const date = new Date(dateString);
		return date.toLocaleString("en-US", {
			year: "numeric",
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		});
	}
</script>

<div id="main" class={theme}>
	<div class="header">
		{#if form.form_annotation_reference_id}
			<span>[{form.form_annotation_reference_id} → {form.id}]</span>
		{:else}
			<span>[{form.id}]</span>
		{/if}

		<span>{formatDateTime(date)}</span>
	</div>
	<div class="header" id="buttons" class:removing>
		<div>{form.creator?.name}</div>

		<div id="button">
			<button onclick={() => openInNewWindow(form)}>
				Open {formSchema.name}
			</button>
		</div>

		<div id="icons">
			<PanelIcon onclick={duplicate} tooltip="Copy" {theme}>
				<Duplicate />
			</PanelIcon>
			<PanelIcon
				onclick={deleteAnnotation}
				tooltip="Delete"
				disabled={!canEditForm}
				{theme}
			>
				<Trash />
			</PanelIcon>
		</div>
	</div>
	{#if removing}
		<div>
			Deleting annotation {form.id}
		</div>
		<progress max={maxTime} value={progress}></progress>
		<div>
			<button
				onclick={() => {
					clearInterval(removing);
					removing = undefined;
				}}
			>
				Cancel
			</button>
		</div>
	{/if}
</div>

<style lang="scss">
	.light {
		background-color: rgba(248, 250, 252, 0.5);
		color: rgb(2 9 65);
		border: 1px solid rgba(0, 0, 0, 0.2);

		button {
			color: rgb(2 9 65);
			border: 1px solid rgba(0, 0, 0, 0.2);
			background-color: rgba(0, 0, 0, 0.01);
		}

		button:hover {
			background-color: rgba(0, 0, 0, 0.05);
		}

		div.header {
			color: rgba(0, 0, 0, 0.6);
		}
	}

	.dark {
		background-color: rgb(0, 0, 0);
		color: rgb(255, 255, 255);
		border: 1px solid rgba(255, 255, 255, 0.3);

		button {
			color: rgba(255, 255, 255, 0.8);
			border: 1px solid rgba(255, 255, 255, 0.1);
			background-color: rgba(255, 255, 255, 0.2);
		}

		button:hover {
			background-color: rgba(255, 255, 255, 0.3);
		}

		div.header {
			color: rgba(255, 255, 255, 0.5);
		}
	}

	div {
		display: flex;
	}

	div.removing {
		opacity: 0.5;
	}

	button {
		cursor: pointer;
		padding: 0.2em;
		border-radius: 2px;
		margin: 0.2em;
		text-wrap-mode: nowrap;
	}

	div#main {
		flex-direction: column;
		flex: 1;
		border-radius: 1px;
		margin-bottom: 0.5em;
		padding: 0.2em;
		font-size: x-small;
	}

	div.header {
		justify-content: space-between;
		align-items: center;
	}
	div#buttons {
		display: flex;
		align-items: center;
	}
	div#buttons > div {
		flex: 1;
	}
	div#icons {
		display: flex;
		justify-content: right;
	}
</style>
