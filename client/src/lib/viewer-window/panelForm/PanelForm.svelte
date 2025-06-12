<script lang="ts">
	import { getContext } from 'svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import type { TaskContext } from '$lib/types';
	import { data } from '$lib/datamodel/model';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import type { FormSchema } from '$lib/datamodel/formSchema.sveltets';
	import FormItem from './FormItem.svelte';
    import type { GlobalContext } from '$lib/data-loading/globalContext.svelte';
    
    const globalContext = getContext<GlobalContext>('globalContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { creator, annotationsFilter, formShortcut } = globalContext;
	const { formSchemas, formAnnotations } = data;

	const {
		image: { instance }
	} = viewerContext;

	const taskContext = getContext<TaskContext>('taskContext');

	//TODO: this should be part of the config?
	const exclude = new Set([
		'ETDRS-grid coordinates',
		'Pointset registration',
		'Affine registration',
		'RegistrationSet'
	]);

	const allSchemas = formSchemas.filter((schema) => !exclude.has(schema.name)).$;
	let selectedSchema: FormSchema | undefined = $state();

	const filters = [
		(annotation: FormAnnotation) => annotation.patient === instance.patient, //same patient
		(annotation: FormAnnotation) => annotation.instance?.laterality == instance.laterality, // same eye
		(annotation: FormAnnotation) => annotation.study == instance.study, // same study
		(annotation: FormAnnotation) => !exclude.has(annotation.formSchema.name)
	];

	// TODO: refactor this, to be used as extension?
	if (taskContext) {
		const TaskDefinitionName = taskContext.task.definition.name;
		if (TaskDefinitionName === 'Naevi') {
			selectedSchema = formSchemas.find((schema) => schema.name === 'Naevi grading');
		} else if (TaskDefinitionName === 'ETDRS-grid placement') {
			selectedSchema = formSchemas.find((schema) => schema.name === 'ETDRS-grid coordinates');
			filters.push((annotation: FormAnnotation) => annotation.instance == instance);
		} else if (TaskDefinitionName === 'Glaucoma grading') {
			selectedSchema = formSchemas.find((schema) => schema.name === 'Glaucoma grading');
		}
	}

	const forms = formAnnotations
		.filter((annotation) => filters.every((filter) => filter(annotation)))
        .filter(annotationsFilter) 
		.sort((a, b) => a.id - b.id);

	async function addForm() {
		if (!selectedSchema) return;
		const item: any = {
			formSchema: selectedSchema,
			patient: instance.patient,
			study: instance.study,
			instance,
			creator
		};
		if (taskContext) {
			item.subTask = taskContext.subTask;
		}
		formAnnotations.create(item);
	}

	let formShortcutSchema = $derived(
		formSchemas.find((schema) => schema.name === formShortcut)
	);
	async function addShortcut() {
		const item: any = {
			formSchema: formShortcutSchema,
			patient: instance.patient,
			study: instance.study,
			instance,
			creator
		};
		if (taskContext) {
			item.subTask = taskContext.subTask;
		}
		formAnnotations.create(item);
	}
</script>

<div class="main">
	<div class="new-form">
		<div>
			<select bind:value={selectedSchema}>
				<option value={undefined}>-- select form type --</option>
				{#each allSchemas as schema}
					<option value={schema}>{schema.name}</option>
				{/each}
			</select>
		</div>

		<div>
			<button onclick={addForm} disabled={!selectedSchema}> Create new form </button>
		</div>

		{#if formShortcutSchema}
			<div>
				<button onclick={addShortcut}> Create {formShortcut} </button>
			</div>
		{/if}
	</div>
	<div>
		{#each $forms as form, i (i)}
			<FormItem {form} />
		{/each}
	</div>
</div>

<style>
	.main {
		display: flex;
		flex-direction: column;
		padding: 0.5em;
		flex: 1;
	}
	div.new-form {
		display: flex;
		flex-direction: column;
		padding: 0.5em;
	}
	button {
		margin-top: 0.5em;
	}
	button {
		color: rgba(255, 255, 255, 0.8);
		padding: 0.2em;
		border: 1px solid rgba(255, 255, 255, 0.1);
		background-color: rgba(255, 255, 255, 0.2);
		border-radius: 2px;
	}
	button:disabled {
		cursor: not-allowed;
		opacity: 0.3;
	}
	button:not(:disabled):hover {
		cursor: pointer;
		background-color: rgba(255, 255, 255, 0.3);
	}
</style>
