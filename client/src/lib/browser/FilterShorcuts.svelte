<script lang="ts">
	import SelectWithSearch from '$lib/components/SelectWithSearch.svelte';
	import * as Button from '$lib/components/ui/button';
	import * as Input from '$lib/components/ui/input';
	import { getContext } from 'svelte';
	import { BrowserContext, type Condition } from './browserContext.svelte';

	const browserContext = getContext<BrowserContext>('browserContext');

	let patientIdentifier = $state('')
	let studyDate = $state('')
	let projectName = $state('')

	function c(variable: Condition['variable'], value: string): Condition[] {
		return [{ variable, operator: '==', value }];
	}

	async function submitPatientIdentifier() {
		if (!patientIdentifier) return;
		
		await browserContext.fetch(c('Patient Identifier', patientIdentifier));
	}

	async function submitDate(e: Event) {
		if (!studyDate) return;
		await browserContext.fetch(c('Study Date', studyDate));
	}

	async function submitProjectName() {
		if (!projectName) return;
		await browserContext.fetch(c('Project Name', projectName));
	}

	const projectOptions = $derived(
		browserContext.getValueOptions('Project Name').map(v => ({ label: v, value: v }))
	);
</script>

<div>
	<form>
		<label>Patient Identifier:</label>
		<Input.Input bind:value={patientIdentifier} placeholder="Patient Identifier" />
		<Button.Button type="submit" onclick={submitPatientIdentifier}>Search</Button.Button>
	</form>

	<form>
		<label>Study Date:</label>
		<Input.Input type="date" bind:value={studyDate} />
		<Button.Button type="submit" disabled={!studyDate} onclick={submitDate}>Search</Button.Button>
	</form>

	<form>
		<label>Project Name:</label>
		<SelectWithSearch 
			options={projectOptions} 
			bind:value={projectName} 
			placeholder="Project Name" 
		/>
		<Button.Button type="submit" disabled={!projectName} onclick={submitProjectName}>Search</Button.Button>
	</form>
</div>

<style>
	div {
		display: grid;
		grid-template-columns: 0fr 16em 0fr;
	}
	label {
		display: flex;
		padding-right: 1em;
		align-items: center;
	}
	form {
		display: contents;
	}
</style>
