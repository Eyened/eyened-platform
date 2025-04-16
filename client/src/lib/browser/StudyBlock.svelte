<script lang="ts">
	import Eye from './Eye.svelte';
	import Icon from '$lib/gui/Icon.svelte';
	import type { Study } from '$lib/datamodel/study';
	import { studyBlockExtensions } from '$lib/extensions';

	interface Props {
		study: Study;
		mode?: 'full' | 'overlay';
	}

	let { study, mode = 'full' }: Props = $props();

	let collapse = $state(false);

	const age = Math.floor((study.date - study.patient.birthDate) / (1000 * 60 * 60 * 24 * 365.25));
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main block">
	<div class="header" onclick={() => (collapse = !collapse)}>
		{#if !collapse}
			▼
		{:else}
			►
		{/if}
		<div class="patient-info">
			<Icon icon="patient" />
			<div class="sex-age">
				{study.patient.sex}
				{age}
			</div>
		</div>

		<div>{study.patient.identifier}</div>

		<Icon icon="calendar" />
		<div>
			{study.date.toISOString().slice(0, 10)}
		</div>
	</div>
	<div class:collapse class="eyes">
		<div>
			<Eye laterality="R" {study} />
			<Eye laterality="L" {study} />
		</div>

		{#if mode == 'full'}
			{#each studyBlockExtensions as extension}
				<extension.component {study} {...extension.props} />
			{/each}
		{/if}
	</div>
</div>

<style>
	div.block {
		padding: 0.3em;
		flex-direction: column;
		border: 1px solid rgb(181, 188, 206);
		border-radius: 2px;
		box-shadow: rgba(149, 157, 165, 0.2) 0px 6px 12px;
		margin-bottom: 1em;
	}

	div {
		display: flex;
	}
	div.header {
		font-size: x-large;
		font-weight: bold;
		cursor: pointer;
		align-items: center;
	}
	div.header > div {
		margin: 0.2em;
		align-items: center;
	}
	div.header:hover {
		background-color: lightgray;
	}
	div.patient-info {
		display: flex;
		flex-direction: column;
	}
	div.sex-age {
		font-size: small;
		font-weight: normal;
	}
	div.collapse {
		display: none;
	}
	div.eyes {
		flex-direction: column;
	}
</style>
