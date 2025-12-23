<script lang="ts">
	import SelectWithSearch from "$lib/components/SelectWithSearch.svelte";
	import * as Input from "$lib/components/ui/input";
	import { getContext, onMount, tick } from "svelte";
	import DatePicker from "../components/DatePicker.svelte";
	import { BrowserContext, type Condition } from "./browserContext.svelte";

	const browserContext = getContext<BrowserContext>("browserContext");

	// bindable single basic condition - this is the root state
	let { condition = $bindable<Condition | null>(null) } = $props();

	// Factory to generate getter/setter objects for condition variable equality
	function conditionValueAccessor(variable: string) {
		return {
			get value() {
				return condition?.variable === variable
					? String(condition.value ?? "")
					: "";
			},
			set value(val: string) {
				condition = val
					? { variable, operator: "==", value: val }
					: null;
			},
		};
	}

	const patientIdentifier = conditionValueAccessor("Patient Identifier");
	const studyDate = conditionValueAccessor("Study Date");
	const projectName = conditionValueAccessor("Project Name");


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
		browserContext
			.getValueOptions("Project Name")
			.map((v) => ({ label: v, value: v })),
	);
</script>

<form onsubmit={handleSubmit}>
	<div
		class="w-full grid grid-cols-[max-content_1fr] gap-x-2 gap-y-1 items-center"
	>
		<!-- Inputs bind to getter/setter objects that derive from condition -->
		<label>Patient Identifier:</label>
		<Input.Input
			bind:value={patientIdentifier.value}
			placeholder="Patient Identifier"
			bind:ref={patientInputRef}
		/>

		<label>Study Date:</label>
		<DatePicker bind:value={studyDate.value} />

		<label>Project Name:</label>
		<SelectWithSearch
			options={projectOptions}
			bind:value={projectName.value}
			placeholder="Project Name"
		/>
	</div>
</form>
