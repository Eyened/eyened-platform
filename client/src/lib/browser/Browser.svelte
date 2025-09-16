
<script lang="ts">
	import { page } from '$app/state';
	import Selection from '$lib/browser/Selection.svelte';
	
	import MySelect from '$lib/components/MySelect.svelte';
	import * as Button from '$lib/components/ui/button';
	import * as Card from "$lib/components/ui/card";
	import type { GlobalContext } from '$lib/data/globalContext.svelte';
// import { showUserMenu } from '$lib/stores.svelte'
	import { getContext, onMount, setContext } from 'svelte';
	import Spinner from '../utils/Spinner.svelte';
	import AdvancedFilters from './AdvancedFilters.svelte';
	import BrowserContent from './BrowserContent.svelte';
	import { BrowserContext, decodeConditions } from './browserContext.svelte';
	import FilterShorcuts from './FilterShorcuts.svelte';
	import Pagination from './Pagination.svelte';
	
	const { user, openAPISpec } = getContext<GlobalContext>('globalContext');
	const initials = user.username
		.split(' ')
		.map((name) => name[0])
		.join('');

	const browserContext: BrowserContext = new BrowserContext();
	setContext('browserContext', browserContext);

	onMount(async () => {
		initParamState();
		await browserContext.loadSignatures();
		// After signatures are in state, optionally kick off a search if there are pre-existing conditions
		if (browserContext.conditions.length) {
			await browserContext.search();
		}
	});

	function initParamState() {
		// read the query string into state
		const params = page.url.searchParams;
		// Retrieve the query parameters from the URL
		browserContext.loadConditions(decodeConditions(params.get('conditions') || ''));
		browserContext.page = parseInt(params.get('page') || '0');
		browserContext.limit = parseInt(params.get('limit') || '100');
	}

	function onPageChange(pageNum: number) {
		browserContext.page = pageNum;
		browserContext.fetch(browserContext.conditions);
	}

	function changeStudyMode(md: any) {
		browserContext.queryMode = md.value;
		console.log(browserContext.queryMode)
	}

	let limitOptions = $derived((browserContext.displayMode === 'instance') ? [50, 100, 200, 500] : [10,20,30,40,50]);

	// let sortByColumns = $derived((browserContext.displayMode === 'instance') ? ['CFQuality', 'StudyDate', 'PatientIdentifier', 'BirthDate', 'DateInserted', 'DateModified'] : ['StudyDate', 'PatientIdentifier', 'BirthDate'])
	let sortByColumns = $derived((browserContext.displayMode === 'instance') ? openAPISpec.components.schemas.SearchQuery.properties.order_by.enum : openAPISpec.components.schemas.StudySearchQuery.properties.order_by.enum);

	// Handle limit as string for MySelect component
	let limitAsString = $state(String(browserContext.limit));
	
	$effect(() => {
		limitAsString = String(browserContext.limit);
	});
	
	$effect(() => {
		if (limitAsString && limitAsString !== String(browserContext.limit)) {
			browserContext.limit = parseInt(limitAsString);
		}
	});

	

</script>

{#if browserContext.loading}
	<div class="loader">
		<div>
			<Spinner />
		</div>
	</div>
{/if}


<div id="container">
	<div id="main">
		<div id="browser-header">
			<div id="browser-header-left">
				<Button.Root
					variant="secondary"
					on:click={() => (browserContext.filterMode = browserContext.filterMode === 'basic' ? 'advanced' : 'basic')}
					aria-pressed={browserContext.filterMode === 'advanced'}
				>
					{browserContext.filterMode === 'advanced' ? 'Advanced Filters v' : 'Advanced Filters >'}
				</Button.Root>
				
				{#if browserContext.filterMode === 'basic'}
					<FilterShorcuts />
				{:else}
					{#if browserContext.activeSignature.length}
						<AdvancedFilters
							signature={browserContext.activeSignature.map(s => ({ 
								name: s.name, 
								values: typeof s.values === 'number' ? String(s.values) : s.values 
							}))}
							bind:conditions={browserContext.conditions}
						/>
					{/if}
				{/if}
			</div>
			<div id="browser-header-right">
				<Card.Root>
					
					<Card.Content class="align-middle grid grid-cols-2 gap-4">

						<label for="queryType">Query: </label>
						<MySelect 
							options={[{value: 'instances', label: 'Instances'}, {value: 'studies', label: 'Studies'}]} 
							bind:value={browserContext.queryMode}
							disabled={false}
							placeholder="Query Type"/>

						{#if browserContext.queryMode === 'instances'}
							<label for="displayMode">Display: </label>
							<MySelect 
								options={[{value: 'instance', label: 'Instances'}, {value: 'partialStudy', label: 'Partial Studies'}, {value: 'fullStudy', label: 'Full Studies'}]} 
								bind:value={browserContext.displayMode}
								disabled={false}
								placeholder="Render Mode"/>							
						{/if}

						<label for="sortBy">Sort: </label>
						<div>
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

						<label for="limit">Items per page: </label>

						<MySelect 
								options={limitOptions.map(opt => ({value: String(opt), label: opt}))} 
								bind:value={limitAsString}
								disabled={false}
								placeholder="Per page"/>
						<!-- Instances <Switch onCheckedChange={toggleStudyMode} /> Studies -->
					</Card.Content>
			
				</Card.Root>
				<!-- <AdvancedFiltering /> -->
				<!-- <FilterConditions /> -->
			</div>
			<div id="user">
				<!-- <MainIcon on:click={() => (globalContext.showUserMenu = true)} tooltip={creator.name} style="light">
					<span class="icon">{initials}</span>
				</MainIcon> -->
			</div>
		</div>
	</div>

	<div id="content">
		<Pagination onChange={onPageChange}/>
		<BrowserContent/>
		<Pagination onChange={onPageChange}/>
	</div>
	<div id="selection">
		<Selection />
	</div>
</div>
<!-- <OptioWindow /> -->
<!-- <InstanceInfo /> -->

<style>
	.loader {
		height: 100vh;
		width: 100vw;
		position: fixed; /* Stay in place */
		z-index: 1; /* Sit on top */
		left: 0;
		top: 0;
		background-color: rgba(255, 255, 255, 0.7); /* Black w/opacity */
		backdrop-filter: blur(5px); /* Filter effect */
	}
	.loader > div {
		position: absolute;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
	}
	div#browser-header {
		display: flex;
	}
	div#browser-header {
		flex: 1;
	}

	div#container {
		height: 100vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	div#container > div {
		flex: 0;
	}
	div#container > div#content {
		padding: 1em;
		overflow-y: auto;
		flex: 1;
	}
	div#main {
		flex: 1;
		background-color: #d7d7d7;
		font-size: 0.8em;
		border-bottom: 3px solid #f1f1f1;
	}
	div#browser-header-left,
	div#browser-header-right {
		flex: 1;
		padding: 1em;
	}
	div#user {
		flex: 0;
		padding: 1em;
	}

	div#selection {
		flex: 0;
	}

	span.icon {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.2em;
		width: 2em;
		height: 2em;
		margin: auto;
		/* font-size: large; */
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 50%;
		font-weight: bold;
	}
	span.icon:hover {
		background-color: rgba(178, 229, 253, 0.5);
	}
</style>
