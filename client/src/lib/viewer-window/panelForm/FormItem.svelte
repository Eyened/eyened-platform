<script lang="ts">
	import FormItemContent from './FormItemContent.svelte';
	import { PanelIcon, Trash } from '../icons/icons';
	import { data } from '$lib/datamodel/model';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import { openNewWindow } from '$lib/newWindow';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext, onDestroy } from 'svelte';
	import { GlobalContext } from '$lib/data-loading/globalContext.svelte';
	import Duplicate from '../icons/Duplicate.svelte';
	import type { TaskContext } from '$lib/types';

	const globalContext = getContext<GlobalContext>('globalContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
	const taskContext = getContext<TaskContext>('taskContext');

	interface Props {
		form: FormAnnotation;
	}

	let { form }: Props = $props();
	const { formAnnotations } = data;

	const dt = new Date().getTime() - form.created;
	const daysSinceCreation = dt / (1000 * 60 * 60 * 24);
	const canEdit = globalContext.canEdit(form);

	let removing: number | undefined = $state();
	let progress = $state(0);
	let maxTime = 3000; // 3 seconds

	function deleteAnnotation() {
		progress = 0;
		removing = setInterval(() => {
			progress += 10;
			if (progress >= maxTime) {
				clearInterval(removing);
				removing = undefined;
				formAnnotations.delete(form);
			}
		}, 10);
	}
	function duplicate() {
		const item: any = { ...form };
		item.creator = globalContext.creator;
		if (taskContext) {
			item.subTask = taskContext.subTask;
		} else {
			item.subTask = undefined;
		}
		item.reference = form;
		formAnnotations.create(item);
	}

	let window: Window | null = null;
	function openInNewWindow(form: FormAnnotation) {
		if (window) {
			window.close();
		}
		const props = { form, viewerContext, canEdit };

		window = openNewWindow(FormItemContent, props, `${form.formSchema.name} ${form.id}`);
	}

	function formatDateTime(dateString: string) {
		const date = new Date(dateString);
		return date.toLocaleString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<div id="main">
	<div class="header" class:removing>
		{#if form.reference}
			<span>[{form.reference.id} → {form.id}]</span>
		{:else}
			<span>[{form.id}]</span>
		{/if}

		<span>{form.creator.name}</span>
		<span>
			<PanelIcon onclick={duplicate} tooltip="Copy">
				<Duplicate />
			</PanelIcon>
			<PanelIcon onclick={deleteAnnotation} tooltip="Delete" disabled={!canEdit}>
				<Trash />
			</PanelIcon>
		</span>
	</div>
	<div class="header">
		<span>{formatDateTime(form.created)}</span>
	</div>
	{#if removing}
		<div>
			Deleting annotation {form.id}
		</div>
		<progress max={maxTime} value={progress}></progress>
		<button
			onclick={() => {
				clearInterval(removing);
				removing = undefined;
			}}>Cancel</button
		>
	{:else}
		<button class="title" onclick={() => openInNewWindow(form)}>{form.formSchema.name}</button>
	{/if}
</div>

<style>
	div {
		display: flex;
	}
	div.removing {
		opacity: 0.5;
	}
	button {
		cursor: pointer;
		color: rgba(255, 255, 255, 0.8);
		padding: 0.2em;
		border: 1px solid rgba(255, 255, 255, 0.1);
		background-color: rgba(255, 255, 255, 0.2);
		border-radius: 2px;
		margin: 0.2em;
	}
	button:hover {
		background-color: rgba(255, 255, 255, 0.3);
	}
	div#main {
		display: flex;
		flex-direction: column;
		flex: 1;
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 2px;
		margin: 0.1em;
		margin-bottom: 0.5em;
		background-color: rgba(255, 255, 255, 0.15);
	}
	div.header {
		justify-content: space-between;
		align-items: center;
	}
	div.header > span {
		padding-left: 0.3em;
		font-size: x-small;
		color: rgba(255, 255, 255, 0.5);
	}
</style>
