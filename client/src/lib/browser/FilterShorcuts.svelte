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
	
	// Track previous values to detect which field changed
	let prev = $state({ patient: '', date: '', project: '' });

	// Single effect: clear other fields when one changes, and set condition
	$effect(() => {
		// Check which field changed
		if (patientIdentifier !== prev.patient) {
			if (patientIdentifier) {
				studyDate = '';
				projectName = '';
			}
			prev.patient = patientIdentifier;
		} else if (studyDate !== prev.date) {
			if (studyDate) {
				patientIdentifier = '';
				projectName = '';
			}
			prev.date = studyDate;
		} else if (projectName !== prev.project) {
			if (projectName) {
				patientIdentifier = '';
				studyDate = '';
			}
			prev.project = projectName;
		}
		
		// Set condition based on which field has a value
		if (patientIdentifier) {
			condition = { variable: 'Patient Identifier', operator: '==', value: patientIdentifier };
		} else if (studyDate) {
			condition = { variable: 'Study Date', operator: '==', value: studyDate };
		} else if (projectName) {
			condition = { variable: 'Project Name', operator: '==', value: projectName };
		} else {
			condition = null;
		}
	});

	// Form submit handler
	function handleSubmit(e: Event) {
		e.preventDefault();
		browserContext.search();
	}

	// Input ref for auto-focus
	let patientInputRef = $state<HTMLInputElement | null>(null);

	// Focus on page load
	onMount(async () => {
		await tick();
		patientInputRef?.focus();
	});

	const projectOptions = $derived(
		browserContext.getValueOptions('Project Name').map(v => ({ label: v, value: v }))
	);
</script>

<form onsubmit={handleSubmit}>
	<div class="w-full grid grid-cols-[max-content_1fr] gap-x-2 gap-y-1 items-center">
		<!-- Inputs bind to state, single effect derives condition -->
		<label>Patient Identifier:</label>
		<Input.Input 
			bind:value={patientIdentifier} 
			placeholder="Patient Identifier" 
			bind:ref={patientInputRef}
		/>

		<label>Study Date:</label>
		<DatePicker bind:value={studyDate} />

		<label>Project Name:</label>
		<SelectWithSearch 
			options={projectOptions} 
			bind:value={projectName} 
			placeholder="Project Name"
		/>
	</div>
</form>