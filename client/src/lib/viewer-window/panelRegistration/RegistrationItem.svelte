<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { globalContext } from '$lib/main';
	import { PanelIcon, Trash } from '../icons/icons';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import { data } from '$lib/datamodel/model';
	import { RegistrationTool } from '$lib/viewer/tools/Registration';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';

	interface Props {
		formAnnotation: FormAnnotation;
		active: boolean;
		activator: { activeID: number | undefined; toggle: (formAnnotation: FormAnnotation) => void };
	}
	let { formAnnotation, active: panelActive, activator }: Props = $props();
	const canEditForm = globalContext.canEdit(formAnnotation);

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const instance = viewerContext.image.instance;
    console.log(formAnnotation.value);
	const item = formAnnotation.value.value;
	const pointSet = item[instance.id] || [];

	const tool = new RegistrationTool(pointSet, (p) => {
		item[instance.id] = p;
		formAnnotation.value.setValue(item);
	});

	let removeTool = () => {};
	onDestroy(() => removeTool());
	let active = $derived(panelActive && activator.activeID === formAnnotation.id);
	$effect(() => {
		if (active) {
			removeTool = viewerContext.addOverlay(tool);
		} else {
			removeTool();
		}
	});

	function remove() {
		activator.activeID = undefined;
		// TODO: should remove from registration?
		data.formAnnotations.delete(formAnnotation);
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<li class="outer" class:active onclick={() => activator.toggle(formAnnotation)}>
	<div class="info">
		<span class="creator">
			{formAnnotation.creator.name}
		</span>
		<span class="annotationID">[{formAnnotation.id}]</span>
		{#if canEditForm}
			<PanelIcon onclick={remove} tooltip="Remove">
				<Trash />
			</PanelIcon>
		{/if}
	</div>
	{#if active}
		{#each Object.entries(formAnnotation.value.value || {}) as [instanceID, pointSet]}
			<div>{instanceID}:</div>
			{#if instanceID === `${instance.id}`}
				<ol>
					{#each pointSet as point}
						{#if point}
							<li class="point">
								{point.x.toFixed(2)}, {point.y.toFixed(2)}
							</li>
						{:else}
							<li class="point">No point</li>
						{/if}
					{/each}
				</ol>
			{/if}
		{/each}
	{/if}
	<div class="linked-images">
		<!-- {#each $annotationDatas as annotationData}
			<RegistrationItemImageIds {annotationData} />
		{/each} -->
	</div>
</li>

<style>
	div {
		display: flex;
	}
	div.info {
		align-items: center;
	}
	div.info * {
		display: flex;
	}
	.creator {
		flex: 1;
	}
	.annotationID {
		color: rgba(255, 255, 255, 0.4);
	}
	li.outer:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
	li.outer {
		cursor: pointer;
		background-color: rgba(255, 255, 255, 0.1);
		padding-left: 0.5em;
		margin-bottom: 0.1em;
		border-radius: 1px;
	}

	li.outer.active {
		background-color: rgb(57, 158, 165);
		color: white;
	}
	li.point {
	}
</style>
