<script lang="ts">
	import MultiSelectWithSearch from '$lib/components/MultiSelectWithSearch.svelte';
	import SelectWithSearch from '$lib/components/SelectWithSearch.svelte';
	import * as Button from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as Input from '$lib/components/ui/input';
	import { faPlus, faTrash } from '@fortawesome/free-solid-svg-icons';
	import { nanoid } from 'nanoid';
	import Fa from 'svelte-fa';

	// Local type definitions until openapi types are regenerated
	type ConditionOperator = '>' | '<' | '>=' | '<=' | '==' | '!=' | 'IN';
	type ConditionValue = string | number | string[] | null;
	
	interface Condition {
		variable: string;
		operator: ConditionOperator;
		value: ConditionValue;
	}

	interface SignatureField {
		name: string;
		values: string | string[]; // 'string' | 'int' | 'float' | 'date' | string[]
	}

	// Internal row state for UI
	interface FilterRow {
		id: string;
		field?: string;
		operator?: ConditionOperator;
		value?: string | number | string[];
	}

	type Props = {
		signature: SignatureField[];
		conditions?: Condition[];
	};

	let { signature, conditions = $bindable([]) }: Props = $props();

	// Internal rows state
	let rows: FilterRow[] = $state([{ id: nanoid() }]);

	// Field options for SelectWithSearch
	const fieldOptions = $derived(
		signature.map(s => ({ label: s.name, value: s.name }))
	);

	// Get signature info for a field
	function getFieldSignature(fieldName: string): SignatureField | undefined {
		return signature.find(s => s.name === fieldName);
	}

	// Get operator options for a field
	function getOperatorOptions(fieldName?: string): ConditionOperator[] {
		if (!fieldName) return [];
		
		const sig = getFieldSignature(fieldName);
		if (!sig) return [];

		// If values is an array (enum), only IN operator
		if (Array.isArray(sig.values)) {
			return ['IN'];
		}

		// For type markers
		switch (sig.values) {
			case 'string':
				return ['=='];
			case 'int':
			case 'float':
			case 'date':
				return ['>', '<', '=='];
			default:
				return ['=='];
		}
	}

	// Get value options for enum fields
	function getValueOptions(fieldName?: string): { label: string; value: string }[] {
		if (!fieldName) return [];
		
		const sig = getFieldSignature(fieldName);
		if (!sig || !Array.isArray(sig.values)) return [];

		return sig.values.map(v => ({ label: v, value: v }));
	}

	// Handle field change
	function onFieldChange(row: FilterRow, newField: string) {
		row.field = newField;
		const operatorOptions = getOperatorOptions(newField);
		row.operator = operatorOptions[0];
		
		const sig = getFieldSignature(newField);
		if (sig && Array.isArray(sig.values)) {
			row.value = [];
		} else {
			row.value = '';
		}
	}

	// Add new row
	function addRow() {
		rows = [...rows, { id: nanoid() }];
	}

	// Remove row
	function removeRow(rowId: string) {
		rows = rows.filter(r => r.id !== rowId);
	}

	// Coerce value based on field type
	function coerceValue(value: any, fieldType: string | string[]): ConditionValue {
		if (Array.isArray(fieldType)) {
			return Array.isArray(value) ? value : [];
		}

		switch (fieldType) {
			case 'int':
				return typeof value === 'string' ? parseInt(value, 10) || 0 : value;
			case 'float':
				return typeof value === 'string' ? parseFloat(value) || 0 : value;
			case 'date':
			case 'string':
			default:
				return value;
		}
	}

	// Derive conditions from rows
	let derivedConditions = $derived(
		rows
			.filter(row => row.field && row.operator && row.value !== '' && row.value !== undefined)
			.map(row => {
				const sig = getFieldSignature(row.field!);
				return {
					variable: row.field!,
					operator: row.operator!,
					value: coerceValue(row.value, sig?.values || 'string')
				};
			})
	);

	// Update conditions prop
	$effect(() => {
		conditions = derivedConditions;
	});
</script>

<div class="space-y-4">
	<div class="font-medium text-sm">Advanced Filters</div>
	
	{#each rows as row (row.id)}
		<div class="flex items-center gap-2 p-3 border rounded-lg">
			<!-- Field Selector -->
			<div class="flex-1">
				<SelectWithSearch
					options={fieldOptions}
					bind:value={row.field}
					placeholder="Select field..."
					{...{ onSelect: (value: string) => onFieldChange(row, value) }}
				/>
			</div>

			<!-- Operator Selector -->
			<div class="w-20">
				{#if row.field}
					{@const operatorOptions = getOperatorOptions(row.field)}
					{#if operatorOptions.length === 1}
						<Button.Root variant="outline" disabled class="w-full">
							{operatorOptions[0]}
						</Button.Root>
					{:else}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button.Root variant="outline" class="w-full">
									{row.operator || '=='}
								</Button.Root>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content>
								{#each operatorOptions as op}
									<DropdownMenu.Item onSelect={() => (row.operator = op)}>
										{op}
									</DropdownMenu.Item>
								{/each}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				{:else}
					<Button.Root variant="outline" disabled class="w-full">--</Button.Root>
				{/if}
			</div>

			<!-- Value Input -->
			<div class="flex-1">
				{#if row.field}
					{@const sig = getFieldSignature(row.field)}
					{#if sig && Array.isArray(sig.values)}
						<!-- Multi-select for enum values -->
						<MultiSelectWithSearch
							options={getValueOptions(row.field)}
							bind:values={row.value}
						/>
					{:else if sig?.values === 'date'}
						<!-- Date input -->
						<Input.Root>
							<input
								type="date"
								bind:value={row.value}
								class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
							/>
						</Input.Root>
					{:else if sig?.values === 'int' || sig?.values === 'float'}
						<!-- Number input -->
						<Input.Root>
							<input
								type="number"
								step={sig.values === 'float' ? 'any' : '1'}
								bind:value={row.value}
								class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
							/>
						</Input.Root>
					{:else}
						<!-- Text input -->
						<Input.Root>
							<input
								type="text"
								bind:value={row.value}
								placeholder="Enter value..."
								class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
							/>
						</Input.Root>
					{/if}
				{:else}
					<Input.Root>
						<input
							type="text"
							disabled
							placeholder="Select field first..."
							class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
						/>
					</Input.Root>
				{/if}
			</div>

			<!-- Remove Button -->
			<Button.Root
				variant="outline"
				size="sm"
				on:click={() => removeRow(row.id)}
				disabled={rows.length === 1}
				class="p-2"
			>
				<Fa icon={faTrash} size="sm" />
			</Button.Root>
		</div>
	{/each}

	<!-- Add Filter Button -->
	<Button.Root variant="outline" on:click={addRow} class="w-full">
		<Fa icon={faPlus} class="mr-2" size="sm" />
		Add Filter
	</Button.Root>
</div>

<style>
	

</style>