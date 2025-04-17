<script lang="ts">
	import { page } from '$app/state';
	import { data } from '$lib/datamodel/model';
	import DateRangePicker from './DateRangePicker.svelte';
	import FilterBlock from './FilterBlock.svelte';
	import ConditionsMultiSelect from './ConditionsMultiSelect.svelte';

	let show = $state(false);

	type FilterItem = {
		variable: string;
		name: string;
		values: any[]; //keyof typeof data;
		title: string;
	};
	const modalities = [
		'AdaptiveOptics',
		'ColorFundus',
		'ColorFundusStereo',
		'RedFreeFundus',
		'ExternalEye',
		'LensPhotograph',
		'Ophthalmoscope',
		'Autofluorescence',
		'FluoresceinAngiography',
		'ICGA',
		'InfraredReflectance',
		'BlueReflectance',
		'GreenReflectance',
		'OCT',
		'OCTA'
	];
	const filterBlocks: FilterItem[] = [
		{ variable: 'FeatureName', name: 'name', values: data['features'].values(), title: 'Features' },
		{ variable: 'CreatorName', name: 'name', values: data['creators'].values(), title: 'Creators' },
		// TODO: Fix. Broken after database update
		{
			variable: 'Modality',
			name: 'modality',
			values: modalities.map((k) => ({ modality: k })),
			title: 'Modality'
		},
		{ variable: 'ProjectName', name: 'name', values: data['projects'].values(), title: 'Projects' },
		{
			variable: 'ManufacturerModelName',
			name: 'model',
			values: data['devices'].values(),
			title: 'Camera'
		}
	];

	function search() {
		show = false;
		const url = new URL(page.url);
		location.href = url.toString();
	}
</script>

<button onclick={() => (show = true)}>Advanced search</button>

{#if show}
	<div class="content">
		<div>
			<button onclick={() => (show = false)}>Close</button>
			<button onclick={search}>Search</button>
		</div>
		<div>
			{#each filterBlocks as { variable, name, values, title }}
				<FilterBlock {title}>
					<ConditionsMultiSelect {variable} {values} {name} />
				</FilterBlock>
			{/each}
		</div>

		<FilterBlock title="Study Date">
			<DateRangePicker />
		</FilterBlock>
	</div>
{/if}

<style>
	.content {
		position: fixed;
		z-index: 1;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
		background-color: rgba(255, 255, 255, 0.99); /* Black w/opacity */
		backdrop-filter: blur(5px);
		transition: 0.5s;
		padding: 1em;
		overflow: auto;
	}
</style>
