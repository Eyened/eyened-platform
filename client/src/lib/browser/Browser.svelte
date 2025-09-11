
<script lang="ts">
	import { page as pageStore } from '$app/stores'
	import Selection from '$lib/browser/Selection.svelte'
	
	import MySelect from '$lib/components/MySelect.svelte'
	import * as Card from "$lib/components/ui/card"
	import type { GlobalContext } from '$lib/data/globalContext.svelte'
	import type { Instance } from '$lib/datamodel/instance.svelte'
// import { showUserMenu } from '$lib/stores.svelte'
	import { getContext, onMount, setContext } from 'svelte'
	import { writable, type Writable } from 'svelte/store'
	import Spinner from '../utils/Spinner.svelte'
	import BrowserContent from './BrowserContent.svelte'
	import { BrowserContext, decodeConditions } from './browserContext.svelte'
	import FilterShorcuts from './FilterShorcuts.svelte'
	import Pagination from './Pagination.svelte'
	
	const { creator, openAPISpec } = getContext<GlobalContext>('globalContext');
	const initials = creator.name
		.split(' ')
		.map((name) => name[0])
		.join('');

	const selection: Writable<Instance[]> = writable([]);
	setContext<Writable<Instance[]>>('selection', selection);

	const browserContext: BrowserContext = new BrowserContext();
	const { queryMode, displayMode, loading, page, limit, sort, sortDirection, search, loadConditions } = browserContext;
	setContext('browserContext', browserContext);

	onMount(() => {
		initParamState()
		search()
	});

	function initParamState() {
		// read the query string into state
		const params = $pageStore.url.searchParams;
		// Retrieve the query parameters from the URL
		loadConditions(decodeConditions(params.get('conditions') || ''));
		page.set(parseInt(params.get('page') || '0'));
		limit.set(parseInt(params.get('limit') || '100'));
	}

	function onPageChange(pageNum: number) {
		page.set(pageNum)
		search()
	}

	function changeStudyMode(md: any) {
		queryMode.set(md.value);
		console.log($queryMode)
	}

	$: limitOptions = ($displayMode === 'instance') ? [50, 100, 200, 500] : [10,20,30,40,50]

	// $: sortByColumns = ($displayMode === 'instance') ? ['CFQuality', 'StudyDate', 'PatientIdentifier', 'BirthDate', 'DateInserted', 'DateModified'] : ['StudyDate', 'PatientIdentifier', 'BirthDate']
	$: sortByColumns = ($displayMode === 'instance') ? openAPISpec.components.schemas.SearchQuery.properties.order_by.enum : openAPISpec.components.schemas.StudySearchQuery.properties.order_by.enum

	

</script>

{#if $loading}
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
				<FilterShorcuts />
				<!-- <AdvancedFilters/> -->
				
			</div>
			<div id="browser-header-right">
				<Card.Root>
					
					<Card.Content class="align-middle grid grid-cols-2 gap-4">

						<label for="queryType">Query: </label>
						<MySelect 
							options={[{value: 'instances', label: 'Instances'}, {value: 'studies', label: 'Studies'}]} 
							selected={$queryMode} 
							onSelectedChange={v => {queryMode.set(v)}}/>

						{#if $queryMode === 'instances'}
							<label for="displayMode">Display: </label>
							<MySelect 
								options={[{value: 'instances', label: 'Instances'}, {value: 'partialStudies', label: 'Partial Studies'}, {value: 'fullStudies', label: 'Full Studies'}]} 
								selected={$displayMode} 
								onSelectedChange={v => {displayMode.set(v)}}
								placeholder="Render Mode"/>							
						{/if}

						<label for="sortBy">Sort: </label>
						<div>
						<MySelect 
								options={sortByColumns.map(v => ({value: v, label: v}))} 
								selected={$sort} 
								onSelectedChange={v => {sort.set(v)}}
								placeholder="Sort by Column"/>			
	
						<MySelect 
								options={[{value:'asc', label: 'ASC'}, {value: 'desc', label:'DESC'}]} 
								selected={$sortDirection} 
								onSelectedChange={v => {sortDirection.set(v)}}
								placeholder="Sort order"/>
						</div>

						<label for="limit">Items per page: </label>

						<MySelect 
								options={limitOptions.map(opt => ({value: opt, label: opt}))} 
								selected={$limit} 
								onSelectedChange={v => {limit.set(v)}}
								placeholder="Per page"/>
						<!-- Instances <Switch onCheckedChange={toggleStudyMode} /> Studies -->
					</Card.Content>
			
				</Card.Root>
				<!-- <AdvancedFiltering /> -->
				<!-- <FilterConditions /> -->
			</div>
			<div id="user">
				<!-- <MainIcon on:click={() => showUserMenu.set(true)} tooltip={creator.name} style="light">
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
