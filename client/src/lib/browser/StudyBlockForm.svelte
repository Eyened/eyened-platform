<script lang="ts">
	import type {
		FormAnnotationGET,
		FormSchemaGET,
		StudyGET,
	} from "../../types/openapi_types";
	import { createFormAnnotation } from "$lib/data/api";
	import { formAnnotations } from "$lib/data/stores.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import FormItem from "$lib/viewer-window/panelForm/FormItem.svelte";
	import { Button } from "$lib/components/ui/button";
	import { getContext } from "svelte";

	interface Props {
		title: string;
		formSchema: FormSchemaGET;
		split_laterality: boolean;
		study: StudyGET;
		create_new: boolean;
	}
	let {
		title,
		split_laterality = true,
		study,
		formSchema,
		create_new,
	}: Props = $props();

	const taskContext = getContext<TaskContext | undefined>("taskContext");

	const forms = $derived(
		formAnnotations
			.filter(
				(annotation) =>
					annotation.study_id === study.id &&
					annotation.form_schema_id === formSchema.id,
			)
			.sort((a, b) => a.id - b.id),
	);

	const leftForms = $derived(forms.filter((form) => form.laterality === "L"));

	const rightForms = $derived(forms.filter((form) => form.laterality === "R"));

	async function create(laterality: "L" | "R" | undefined) {
		await createFormAnnotation({
			form_schema_id: formSchema.id,
			patient_id: study.patient.id,
			study_id: study.id,
			laterality: laterality,
			sub_task_id: taskContext?.subTask?.id,
			form_data: {},
		});
	}
</script>

{#snippet form_item(
	laterality: "L" | "R" | undefined,
	forms: FormAnnotationGET[],
	suffix: string = "",
)}
	{#if laterality !== undefined && create_new}
		<div>
			<Button onclick={() => create(laterality)} variant="outline" size="sm">
				Create {formSchema.name}
				{suffix}
			</Button>
		</div>
	{/if}

	{#each forms as form}
		<div>
			<div class="form-item flex flex-col w-[20em]">
				<FormItem {form} theme="light" />
			</div>
		</div>
	{/each}
{/snippet}

<div id="main" class="flex flex-col px-2">
	<h4 class="p-0 m-0 mt-2 mb-2">{title}</h4>
	{#if split_laterality}
		<div id="eyes" class="flex flex-row">
			<div class="flex flex-col flex-1">
				{@render form_item("R", rightForms, "OD")}
			</div>
			<div class="flex flex-col flex-1">
				{@render form_item("L", leftForms, "OS")}
			</div>
		</div>
	{:else}
		{@render form_item(undefined, forms)}
	{/if}
</div>
