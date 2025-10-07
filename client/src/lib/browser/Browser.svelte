
<script lang="ts">
	import { page } from '$app/state';
	import Selection from '$lib/browser/Selection.svelte';
	
	import MySelect from '$lib/components/MySelect.svelte';
	import * as Button from '$lib/components/ui/button';
	import * as Card from "$lib/components/ui/card";
	import type { GlobalContext } from '$lib/data/globalContext.svelte';
	import { getContext, onMount, setContext } from 'svelte';
	import { searchOrderBy, studiesSearchOrderBy } from '../../types/openapi_constants';
	import FixedSpinner from '../components/FixedSpinner.svelte';
	import AdvancedFilters from './AdvancedFilters.svelte';
	import BrowserContent from './BrowserContent.svelte';
	import { BrowserContext, decodeConditions, type QueryMode } from './browserContext.svelte';
	import FilterShorcuts from './FilterShorcuts.svelte';
	
	const globalContext = getContext<GlobalContext>('globalContext');
	const { user } = globalContext;
	const initials = user.username
		.split(' ')
		.map((name) => name[0])
		.join('');

	const browserContext: BrowserContext = new BrowserContext();
	setContext('browserContext', browserContext);

	let initializing = true;

	onMount(async () => {
		initializing = true;
		initParamState();
		await browserContext.loadSignatures();
		// After signatures are in state, optionally kick off a search if there are pre-existing conditions
		await browserContext.search();
		initializing = false;
	});

	function initParamState() {
		// read the query string into state
		const params = page.url.searchParams;
		// Retrieve the query parameters from the URL
		const conds = decodeConditions(params.get('conditions') || '');

		browserContext.page = parseInt(params.get('page') || '0', 10);
		const limitParam = params.get('limit');
		if (limitParam !== null && limitParam !== '') {
			const parsedLimit = parseInt(limitParam, 10);
			if (!Number.isNaN(parsedLimit)) browserContext.limit = parsedLimit;
		}

		// new: query mode and sort
		const qm = params.get('queryMode');
		if (qm === 'instances' || qm === 'studies') browserContext.queryMode = qm;

		const dm = params.get('displayMode');
		if (dm === 'instance' || dm === 'study') browserContext.displayMode = dm;

		const fm = params.get('filterMode');
		if (fm === 'basic' || fm === 'advanced') browserContext.filterMode = fm;
		if (conds.length) {
			if (fm === 'advanced') browserContext.advancedConditions = conds;
			if (fm === 'basic') browserContext.basicCondition = conds[0];
		}


		const ob = params.get('order_by');
		if (ob) browserContext.sortBy = ob as any;

		const od = params.get('order');
		if (od === 'ASC' || od === 'DESC') browserContext.sortDirection = od;
	}


	let limitOptions = $derived(
		(browserContext.queryMode === 'instances' && browserContext.displayMode === 'instance')
			? browserContext.limitOptionsInstances
			: browserContext.limitOptionsStudies
	);

	let sortByColumns = $derived((browserContext.displayMode === 'instance') ? searchOrderBy : studiesSearchOrderBy);

	// Handle limit as string for MySelect component
	let limitAsString = $state(String(browserContext.limit));

	const handleSearch = () => {
		browserContext.page = 0;
		browserContext.search();
	}
	
	$effect(() => {
		limitAsString = String(browserContext.limit);
	});
	
	$effect(() => {
		if (limitAsString && limitAsString !== String(browserContext.limit)) {
			browserContext.limit = parseInt(limitAsString, 10);
		}
	});

	

</script>

{#if browserContext.loading}
	<FixedSpinner />
{/if}


<div id="container">
	<div id="main" class="flex flex-row w-full bg-gray-200 font-sm">
			<div class="flex-5 flex-col min-w-0 p-4">
				{#if browserContext.filterMode === 'basic'}
					<FilterShorcuts bind:condition={browserContext.basicCondition} />
				{:else}
					{#if browserContext.activeSignature.length}
						<AdvancedFilters
							signature={browserContext.activeSignature.map(s => ({ 
								name: s.name, 
								values: typeof s.values === 'number' ? String(s.values) : s.values 
							}))}
							bind:conditions={browserContext.advancedConditions}
						/>
					{/if}
				{/if}

				<div class="">
					<div class="float-right">
					<Button.Root
						variant="link"
						onclick={() => (browserContext.filterMode = browserContext.filterMode === 'basic' ? 'advanced' : 'basic')}
						class="text-xs"
					>
						{browserContext.filterMode === 'advanced' ? 'Basic Filters' : 'Advanced Filters'}
					</Button.Root>
					</div>
				</div>

				<Button.Root
					variant="default"
					onclick={handleSearch}
					class="text-sm mr-2 w-full"
				>
					Search
				</Button.Root>
				
			</div>
			<div class="flex-5 min-w-0 p-4">
				<Card.Root>
					
					<Card.Content class="flex flex-col gap-4">

						<div class="flex-1">
							<div class="flex items-center gap-8">
								<div class="flex items-center gap-2">
									<label for="queryType">Query: </label>
									<MySelect 
										options={[{value: 'instances', label: 'Instances'}, {value: 'studies', label: 'Studies'}]} 
										bind:value={browserContext.queryMode}
										disabled={false}
										onChange={(queryMode) => {
											browserContext.resetForQueryModeChange(queryMode as QueryMode);
										}}
										placeholder="Query Type"/>
								</div>
								{#if browserContext.queryMode === 'instances'}
									<div class="flex items-center gap-2">
										<label for="displayMode">Display: </label>
										<MySelect 
											options={[{value: 'instance', label: 'Instances'},  {value: 'study', label: 'Studies'}]} 
											bind:value={browserContext.displayMode}
											disabled={false}
											placeholder="Render Mode"/>
									</div>
								{/if}
							</div>
						</div>

						<div class="flex-1 flex items-center gap-8">
							<div class="flex items-center gap-2">
								<label for="sortBy">Sort: </label>
								<MySelect 
										options={sortByColumns.map(v => ({value: v, label: v}))} 
										bind:value={browserContext.sortBy}
										disabled={false}
										placeholder="Sort by Column"/>			

								<MySelect 
										options={[{value:'ASC', label: 'ASC'}, {value: 'DESC', label:'DESC'}]} 
										bind:value={browserContext.sortDirection}
										disabled={false}
										placeholder="Sort order"/>
							</div>

							<div class="flex items-center gap-2">
								<label for="limit">Items per page: </label>
								<MySelect 
										options={limitOptions.map(opt => ({value: String(opt), label: opt}))} 
										bind:value={limitAsString}
										disabled={false}
										placeholder="Per page"/>
							</div>
						</div>
						<!-- Instances <Switch onCheckedChange={toggleStudyMode} /> Studies -->
					</Card.Content>
			
				</Card.Root>
				<!-- <AdvancedFiltering /> -->
				<!-- <FilterConditions /> -->
				
			</div>
	
	</div>

	<div id="content" class="p-4">
		<BrowserContent/>
	</div>
	{#if browserContext.selectedIds.length > 0}
		<Selection />
	{/if}
</div>
<!-- <OptioWindow /> -->
<!-- <InstanceInfo /> -->

