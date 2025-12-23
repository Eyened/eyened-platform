<script lang="ts">
	import MultiSelectWithSearch from "$lib/components/MultiSelectWithSearch.svelte";
	import SelectWithSearch from "$lib/components/SelectWithSearch.svelte";
	import * as Button from "$lib/components/ui/button";
	import * as DropdownMenu from "$lib/components/ui/dropdown-menu";
	import { Input } from "$lib/components/ui/input";
	import { faPlus, faTrash } from "@fortawesome/free-solid-svg-icons";
	import Fa from "svelte-fa";
	import { getContext } from "svelte";
	import type {
		AttributeCondition,
		DefaultCondition,
		SearchCondition as SearchConditionT,
		SignatureField as SignatureFieldT,
	} from "../../types/openapi_types";
	import DatePicker from "../components/DatePicker.svelte";
	import { BrowserContext } from "./browserContext.svelte";

	// Use OpenAPI-generated types
	type Condition = SearchConditionT;
	type SignatureField = SignatureFieldT;
	type ConditionOperator = Condition["operator"];
	type ConditionValue = Condition["value"];

	type Props = {
		signature: SignatureField[];
		conditions?: Condition[];
	};

	let { signature, conditions = $bindable() }: Props = $props();
	const browserContext = getContext<BrowserContext>("browserContext");

	// Ephemeral state for adding new conditions
	let draftRow: {
		field?: string;
		operator?: ConditionOperator;
		value?: ConditionValue;
	} | null = $state(null);

	// Field options for SelectWithSearch (grouped)
	function createFieldOption(s: SignatureField) {
		const isAttribute = (s.type ?? "default") === "attribute";

		let label = s.name;
		if (isAttribute && s.feature) {
			label = `${s.name} (${s.feature})`;
		}

		let value = s.name;
		if (isAttribute) {
			const feature = s.feature ?? "none";
			value = `${s.model}__${feature}__${s.name}`;
		}

		let group = "Fields";
		if (isAttribute) {
			if (s.feature) {
				group = `${s.model} (${s.feature})`;
			} else {
				group = s.model ?? "Attributes";
			}
		}

		return { label, value, group };
	}

	const fieldOptions = $derived(signature.map(createFieldOption));

	// Get signature info for a field (handles attribute encoding)
	function getFieldSignature(fieldValue: string): SignatureField | undefined {
		if (!fieldValue.includes("__")) {
			return signature.find((s) => s.name === fieldValue);
		}

		const parts = fieldValue.split("__");
		if (parts.length !== 3) {
			return signature.find((s) => s.name === fieldValue);
		}

		const [model, feature, name] = parts;
		return signature.find((s) => {
			if (s.name !== name || s.model !== model) return false;
			if (feature === "none") {
				return !s.feature;
			}
			return s.feature === feature;
		});
	}

	// Convert condition to encoded field value for dropdown
	function conditionToFieldValue(condition: Condition): string {
		if ((condition as any).type === "attribute") {
			const attrCond = condition as any;
			const model = attrCond.model || "";
			const feature = attrCond.feature ?? "none";
			const name = attrCond.variable;
			return `${model}__${feature}__${name}`;
		}
		return (condition as any).variable;
	}

	// Get operator options for a field
	function getOperatorOptions(fieldName?: string): ConditionOperator[] {
		if (!fieldName) return [];

		const sig = getFieldSignature(fieldName);
		if (!sig) return [];

		const ops: ConditionOperator[] = [];

		if (Array.isArray(sig.values)) {
			ops.push("IN");
		} else {
			if (sig.values === "string") {
				ops.push("==");
			} else if (
				sig.values === "int" ||
				sig.values === "float" ||
				sig.values === "date"
			) {
				ops.push(">", "<", "==");
			} else {
				ops.push("==");
			}
		}

		if ((sig as any).nullable) {
			ops.push("IS NULL" as ConditionOperator);
		}

		return ops;
	}

	// Get value options for enum fields
	function getValueOptions(
		fieldName?: string,
	): { label: string; value: string }[] {
		if (!fieldName) return [];

		const sig = getFieldSignature(fieldName);
		if (!sig || !Array.isArray(sig.values)) return [];

		return sig.values.map((v) => ({ label: v, value: v }));
	}

	// Default operator per field
	function getDefaultOperator(fieldName: string): ConditionOperator {
		const sig = getFieldSignature(fieldName);
		if (!sig) return "==";
		if (Array.isArray(sig.values)) return "IN";
		return "==";
	}

	// Coerce value based on field type
	function coerceValue(
		value: any,
		fieldType: string | string[],
	): ConditionValue {
		if (Array.isArray(fieldType)) {
			return Array.isArray(value) ? value : [];
		}

		if (fieldType === "int") {
			return typeof value === "string" ? parseInt(value, 10) || 0 : value;
		}
		if (fieldType === "float") {
			return typeof value === "string" ? parseFloat(value) || 0 : value;
		}
		return value;
	}

	// Condition update helpers - normalize via browserContext before setting
	function setConditions(next: Condition[]) {
		const normalized = browserContext.normalizeConditions(next);
		conditions = normalized;
	}

	function updateConditionAt(i: number, patch: Partial<Condition>) {
		const next = (conditions ?? []).slice();
		const curr = next[i];
		if (!curr) return;

		const updated: Condition = { ...curr, ...(patch as any) } as Condition;
		next[i] = updated;
		setConditions(next);
	}

	function removeConditionAt(i: number) {
		const next = (conditions ?? []).slice();
		next.splice(i, 1);
		setConditions(next);
	}

	// Draft row helpers
	function startDraft() {
		draftRow = {};
	}

	function cancelDraft() {
		draftRow = null;
	}

	function commitDraftIfValid() {
		if (!draftRow?.field || !draftRow?.operator) return;

		if (draftRow.operator !== "IS NULL") {
			if (
				!draftRow.value ||
				draftRow.value === "" ||
				(Array.isArray(draftRow.value) && draftRow.value.length === 0)
			) {
				return;
			}
		}

		const sig = getFieldSignature(draftRow.field);
		let value = draftRow.value;
		if (draftRow.operator !== "IS NULL" && sig) {
			value = coerceValue(draftRow.value, sig.values);
		}

		const isAttribute = sig && (sig.type ?? "default") === "attribute";
		let newCond: Condition;

		if (isAttribute) {
			newCond = {
				type: "attribute",
				model: sig.model || "",
				variable: sig.name as any,
				operator: draftRow.operator as any,
				value,
				feature: sig.feature ?? undefined,
			} as AttributeCondition;
		} else {
			newCond = {
				type: "default",
				variable: draftRow.field as any,
				operator: draftRow.operator as any,
				value,
			} as DefaultCondition;
		}

		setConditions([...(conditions ?? []), newCond]);
		draftRow = null;
	}

	function updateDraftField(field: string) {
		if (!draftRow) return;
		const sig = getFieldSignature(field);
		draftRow.field = field;
		draftRow.operator = getDefaultOperator(field);
		draftRow.value = Array.isArray(sig?.values) ? [] : "";
		commitDraftIfValid();
	}

	function updateDraftOperator(operator: ConditionOperator) {
		if (!draftRow) return;
		draftRow.operator = operator;
		commitDraftIfValid();
	}

	function updateDraftValue(value: ConditionValue) {
		if (!draftRow) return;
		draftRow.value = value;
		commitDraftIfValid();
	}

	// Handler for field selection in existing condition
	function handleFieldSelect(fieldValue: string, conditionIndex: number) {
		const sig = getFieldSignature(fieldValue);
		const patch: Partial<Condition> = {
			variable: sig?.name || fieldValue,
			operator: getDefaultOperator(fieldValue) as any,
			value: Array.isArray(sig?.values) ? [] : "",
		} as any;

		if (sig && (sig.type ?? "default") === "attribute") {
			(patch as any).type = "attribute";
			(patch as any).model = sig.model || "";
			(patch as any).feature = sig.feature ?? undefined;
		} else {
			(patch as any).type = "default";
		}

		updateConditionAt(conditionIndex, patch);
	}
</script>

<div class="space-y-4">
	{#each conditions || [] as condition, i (condition.variable + String(i))}
		{@const ops = getOperatorOptions(condition.variable)}
		{@const sig = getFieldSignature(condition.variable)}
		<div class="flex items-center gap-2 p-0 border rounded-lg">
			<!-- Field Selector -->
			<div class="flex-1">
				<SelectWithSearch
					options={fieldOptions}
					value={conditionToFieldValue(condition)}
					placeholder="Select field..."
					onSelect={(v: string) => handleFieldSelect(v, i)}
				/>
			</div>

			<!-- Operator Selector -->
			<div class="w-20">
				{#if ops.length === 1}
					<Button.Root variant="outline" disabled class="w-full"
						>{ops[0]}</Button.Root
					>
				{:else}
					<DropdownMenu.Root>
						<DropdownMenu.Trigger>
							<Button.Root variant="outline" class="w-full"
								>{condition.operator}</Button.Root
							>
						</DropdownMenu.Trigger>
						<DropdownMenu.Content>
							{#each ops as op}
								<DropdownMenu.Item
									onSelect={() => updateConditionAt(i, { operator: op as any })}
								>
									{op}
								</DropdownMenu.Item>
							{/each}
						</DropdownMenu.Content>
					</DropdownMenu.Root>
				{/if}
			</div>

			<!-- Value Input -->
			<div class="flex-1">
				{#if condition.operator !== "IS NULL"}
					{#if sig && Array.isArray(sig.values)}
						<MultiSelectWithSearch
							options={getValueOptions(condition.variable)}
							values={(condition.value as string[]) ?? []}
							onselect={(values) => updateConditionAt(i, { value: values })}
						/>
					{:else if sig?.values === "date"}
						<DatePicker
							value={String(condition.value ?? "")}
							onchange={(v) => updateConditionAt(i, { value: v })}
						/>
					{:else if sig?.values === "int" || sig?.values === "float"}
						<Input
							type="number"
							step={sig.values === "float" ? "any" : "1"}
							value={String(condition.value ?? "")}
							oninput={(e: Event) =>
								updateConditionAt(i, {
									value: (e.target as HTMLInputElement).value,
								})}
						/>
					{:else}
						<Input
							type="text"
							value={String(condition.value ?? "")}
							placeholder="Enter value..."
							oninput={(e: Event) =>
								updateConditionAt(i, {
									value: (e.target as HTMLInputElement).value,
								})}
						/>
					{/if}
				{:else}
					<Input disabled value="" />
				{/if}
			</div>

			<!-- Remove Button -->
			<Button.Root
				variant="outline"
				size="sm"
				onclick={() => removeConditionAt(i)}
				class="p-2"
			>
				<Fa icon={faTrash} size="sm" />
			</Button.Root>
		</div>
	{/each}

	<!-- Draft Row -->
	{#if draftRow !== null}
		<div class="flex items-center gap-2 p-0 border rounded-lg bg-muted/50">
			<!-- Field Selector -->
			<div class="flex-1">
				<SelectWithSearch
					options={fieldOptions}
					value={draftRow.field}
					placeholder="Select field..."
					onSelect={updateDraftField}
				/>
			</div>

			<!-- Operator Selector -->
			<div class="w-20">
				{#if draftRow.field}
					{@const ops = getOperatorOptions(draftRow.field)}
					{#if ops.length === 1}
						<Button.Root variant="outline" disabled class="w-full"
							>{ops[0]}</Button.Root
						>
					{:else}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button.Root variant="outline" class="w-full"
									>{draftRow.operator || "=="}</Button.Root
								>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content>
								{#each ops as op}
									<DropdownMenu.Item onSelect={() => updateDraftOperator(op)}>
										{op}
									</DropdownMenu.Item>
								{/each}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				{:else}
					<Button.Root variant="outline" disabled class="w-full">--</Button.Root
					>
				{/if}
			</div>

			<!-- Value Input -->
			<div class="flex-1">
				{#if draftRow.field}
					{#if draftRow.operator !== "IS NULL"}
						{@const sig = getFieldSignature(draftRow.field)}
						{#if sig && Array.isArray(sig.values)}
							<MultiSelectWithSearch
								options={getValueOptions(draftRow.field)}
								values={(draftRow.value as string[]) ?? []}
								onselect={(values) => updateDraftValue(values)}
							/>
						{:else if sig?.values === "date"}
							<DatePicker
								value={String(draftRow.value ?? "")}
								onchange={(v) => updateDraftValue(v)}
							/>
						{:else if sig?.values === "int" || sig?.values === "float"}
							<Input
								type="number"
								step={sig.values === "float" ? "any" : "1"}
								value={String(draftRow.value ?? "")}
								onchange={(e: Event) =>
									updateDraftValue((e.target as HTMLInputElement).value)}
							/>
						{:else}
							<Input
								value={String(draftRow.value ?? "")}
								placeholder="Enter value..."
								onchange={(e: Event) =>
									updateDraftValue((e.target as HTMLInputElement).value)}
							/>
						{/if}
					{:else}
						<Input disabled value="" />
					{/if}
				{:else}
					<Input type="text" disabled placeholder="Select field first..." />
				{/if}
			</div>

			<!-- Cancel Button -->
			<Button.Root
				variant="outline"
				size="sm"
				onclick={cancelDraft}
				class="p-2"
			>
				<Fa icon={faTrash} size="sm" />
			</Button.Root>
		</div>
	{/if}

	<!-- Add Filter Button -->
	<Button.Root
		variant="outline"
		onclick={startDraft}
		disabled={draftRow !== null}
		class="w-full"
	>
		<Fa icon={faPlus} class="mr-2" size="sm" />
		Add Filter
	</Button.Root>
</div>

<style>
</style>
