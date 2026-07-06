<script lang="ts">
	import SelectWithSearch from "$lib/components/SelectWithSearch.svelte";
	import * as Input from "$lib/components/ui/input";
	import { getContext, onMount, tick } from "svelte";
	import DatePicker from "../components/DatePicker.svelte";
	import { BrowserContext, type Condition } from "./browserContext.svelte";

	const browserContext = getContext<BrowserContext>("browserContext");

	// bindable single basic condition - this is the root state
	let { condition = $bindable<Condition | null>(null) } = $props();

	function fieldUsesInOperator(variable: string) {
		return Array.isArray(
			browserContext.activeSignature.find((s) => s.name === variable)
				?.values,
		);
	}

	// Factory to generate getter/setter objects for a single basic filter field
	function conditionValueAccessor(variable: string) {
		return {
			get value() {
				if (condition?.variable !== variable) return "";
				const v = condition.value;
				if (Array.isArray(v)) return v[0] ?? "";
				return String(v ?? "");
			},
			set value(val: string) {
				if (!val) {
					condition = null;
					return;
				}
				condition = fieldUsesInOperator(variable)
					? {
							type: "default",
							variable,
							operator: "IN",
							value: [val],
						}
					: {
							type: "default",
							variable,
							operator: "==",
							value: val,
						};
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
