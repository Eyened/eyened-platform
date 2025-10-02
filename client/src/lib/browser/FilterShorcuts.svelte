<script lang="ts">
	import SelectWithSearch from '$lib/components/SelectWithSearch.svelte';
	import * as Input from '$lib/components/ui/input';
	import { getContext, onMount, tick } from 'svelte';
	import DatePicker from '../components/DatePicker.svelte';
	import { BrowserContext, type Condition } from './browserContext.svelte';

	const browserContext = getContext<BrowserContext>('browserContext');

	// bindable single basic condition
	let { condition = $bindable<Condition | null>(null) } = $props();

	let patientIdentifier = $state('');
	let studyDate = $state('');
	let projectName = $state('');

	function setCondition(c: Condition | null) { condition = c; }

	// NEW: ref and key handler
	let patientInputRef: HTMLInputElement | null = null;
	function onPatientIdentifierKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			browserContext.search();
		}
	}

	// Focus on page load
	onMount(async () => {
		await tick();
		patientInputRef?.focus();
	});

	// Mutually exclusive setters
	$effect(() => {
		if (patientIdentifier) {
			studyDate = '';
			projectName = '';
			setCondition({ variable: 'Patient Identifier', operator: '==', value: patientIdentifier });
		} else if (!studyDate && !projectName) {
			setCondition(null);
		}
	});
	$effect(() => {
		if (studyDate) {
			patientIdentifier = '';
			projectName = '';
			setCondition({ variable: 'Study Date', operator: '==', value: studyDate });
		} else if (!patientIdentifier && !projectName) {
			setCondition(null);
		}
	});
	$effect(() => {
		if (projectName) {
			patientIdentifier = '';
			studyDate = '';
			setCondition({ variable: 'Project Name', operator: '==', value: projectName });
		} else if (!patientIdentifier && !studyDate) {
			setCondition(null);
		}
	});

	const projectOptions = $derived(
		browserContext.getValueOptions('Project Name').map(v => ({ label: v, value: v }))
	);
</script>

<div>
	<div class="w-full grid grid-cols-[max-content_1fr] gap-x-2 gap-y-1 items-center">
		<!-- No submit buttons; inputs only set the bindable condition -->
		<label>Patient Identifier:</label>
		<Input.Input bind:value={patientIdentifier} placeholder="Patient Identifier" bind:ref={patientInputRef} on:keydown={onPatientIdentifierKeydown} />

		<label>Study Date:</label>
		<DatePicker bind:value={studyDate} />
		<!-- <Input.Input type="date" bind:value={studyDate} /> -->

		<label>Project Name:</label>
		<SelectWithSearch 
			options={projectOptions} 
			bind:value={projectName} 
			placeholder="Project Name" 
		/>
	</div>
</div>

<style>
</style>
