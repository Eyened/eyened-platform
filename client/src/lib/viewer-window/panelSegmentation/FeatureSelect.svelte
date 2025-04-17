<script lang="ts">
	import type { Feature } from '$lib/datamodel/feature';

	interface Props {
		values: Feature[];
		onselect: (value: Feature) => void;
	}

	let { values, onselect }: Props = $props();
	export const placeholder = 'Search...';
	let filter = $state('');
	let filtered: Feature[] = $derived.by(() => {
		if (filter) {
			return values.filter((value) => value.name.toLowerCase().includes(filter.toLowerCase()));
		} else {
			return [];
		}
	});
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div>
	<div>
		Create:
		<input type="text" {placeholder} bind:value={filter} />
	</div>
	<ul>
		{#each filtered as feature}
			<li class="item" onclick={() => onselect(feature)}>
				{feature.name}
			</li>
		{/each}
	</ul>
</div>

<style>
	ul {
		padding: 0;
		margin: 0;
		list-style-type: none;
		flex: 0;
	}
	li.item {
		font-size: 0.9em;
		color: rgba(255, 255, 255, 0.5);
		cursor: pointer;
		padding: 0.1em 0.2em;
		margin: 0.1em;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 0.2em;
	}
	li:hover {
		background-color: rgba(255, 255, 255, 0.3);
		cursor: pointer;
	}
</style>
