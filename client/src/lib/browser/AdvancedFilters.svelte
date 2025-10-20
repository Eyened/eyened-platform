<script lang="ts">
	import MultiSelectWithSearch from '$lib/components/MultiSelectWithSearch.svelte';
	import SelectWithSearch from '$lib/components/SelectWithSearch.svelte';
	import * as Button from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { Input } from '$lib/components/ui/input';
	import { faPlus, faTrash } from '@fortawesome/free-solid-svg-icons';
	import Fa from 'svelte-fa';
	import type { AttributeCondition, DefaultCondition, SearchCondition as SearchConditionT, SignatureField as SignatureFieldT } from '../../types/openapi_types';
	import DatePicker from '../components/DatePicker.svelte';

    // Use OpenAPI-generated types
    type Condition = SearchConditionT;
    type SignatureField = SignatureFieldT;
    type ConditionOperator = Condition['operator'];
    type ConditionValue = Condition['value'];

	type Props = {
		signature: SignatureField[];
		conditions?: Condition[];
	};

	let { signature, conditions = $bindable() }: Props = $props();

	// Ephemeral state for adding new conditions
	let draftRow: { field?: string; operator?: ConditionOperator; value?: ConditionValue } | null = $state(null);

    // Field options for SelectWithSearch (grouped)
    const fieldOptions = $derived(
        signature.map(s => ({
            label: s.name,
            value: s.name,
            group: (s.type ?? 'default') === 'attribute' ? (s.model ?? 'Attributes') : 'Fields'
        }))
    );

	$effect(() => {
		console.log('fieldOptions', fieldOptions, signature);
	});

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
	
	// Default operator per field
	function getDefaultOperator(fieldName: string): ConditionOperator {
		const sig = getFieldSignature(fieldName);
		if (!sig) return '==';
		return Array.isArray(sig.values) ? 'IN' : '==';
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

	// Condition update helpers
	function setConditions(next: Condition[]) {
		conditions = next;
	}

	function updateConditionAt(i: number, patch: Partial<Condition>) {
		const next = conditions?.slice() || [];
		const curr = next[i];
		if (!curr) return;
		
        let updated: Condition = { ...curr, ...(patch as any) } as Condition;
		
		// Sanitize operator/value against signature
		const sig = getFieldSignature(updated.variable);
		const allowedOps = getOperatorOptions(updated.variable);
		if (!allowedOps.includes(updated.operator as ConditionOperator)) {
			updated.operator = getDefaultOperator(updated.variable) as any;
		}
		updated.value = coerceValue(updated.value, sig?.values ?? 'string');
		next[i] = updated;
		setConditions(next);
	}

	function removeConditionAt(i: number) {
		const next = conditions?.slice() || [];
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
		if (!draftRow?.field || !draftRow?.operator || (draftRow.value === undefined || draftRow.value === '' || (Array.isArray(draftRow.value) && draftRow.value.length === 0))) return;
		
		const sig = getFieldSignature(draftRow.field);
		const value = coerceValue(draftRow.value, sig?.values ?? 'string');
        const newCond: Condition = (sig && (sig.type ?? 'default') === 'attribute')
            ? ({ type: 'attribute', model: sig?.model || '', variable: draftRow.field as any, operator: draftRow.operator as any, value } as AttributeCondition)
            : ({ type: 'default', variable: draftRow.field as any, operator: draftRow.operator as any, value } as DefaultCondition);
        setConditions([...(conditions ?? []), newCond]);
		draftRow = null;
	}

	function updateDraftField(field: string) {
		if (!draftRow) return;
		const sig = getFieldSignature(field);
		draftRow.field = field;
		draftRow.operator = getDefaultOperator(field);
		draftRow.value = Array.isArray(sig?.values) ? [] : '';
		commitDraftIfValid();
	}

	function updateDraftOperator(operator: ConditionOperator) {
		if (!draftRow) return;
		draftRow.operator = operator;
		commitDraftIfValid();
	}

	function updateDraftValue(value: ConditionValue) {
		if (!draftRow) return;
		console.log('updateDraftValue', value);
		draftRow.value = value;
		commitDraftIfValid();
	}

	// Sanitize conditions when signature or conditions change externally
    $effect(() => {
		if (!conditions) return;
        const next: Condition[] = [];
		for (const c of conditions) {
			const sig = getFieldSignature(c.variable);
			if (!sig) continue; // drop unknown fields for current signature
			const allowedOps = getOperatorOptions(c.variable);
            const operator = allowedOps.includes(c.operator as ConditionOperator) ? c.operator : getDefaultOperator(c.variable);
            const value = coerceValue(c.value, sig.values);
            if ((c as any).type === 'attribute') {
                next.push({ type: 'attribute', model: (c as any).model || '', variable: c.variable as any, operator: operator as any, value } as AttributeCondition);
            } else {
                next.push({ type: 'default', variable: c.variable as any, operator: operator as any, value } as DefaultCondition);
            }
		}
		if (JSON.stringify(next) !== JSON.stringify(conditions)) {
			conditions = next;
		}
	});

</script>

<div class="space-y-4">
	{#each (conditions || []) as condition, i (i)}
		<div class="flex items-center gap-2 p-0 border rounded-lg">
			<!-- Field Selector -->
			<div class="flex-1">
                <SelectWithSearch
                    options={fieldOptions}
                    value={condition.variable}
					placeholder="Select field..."
					onSelect={(v: string) => {
						const sig = getFieldSignature(v);
                        const patch: Partial<Condition> = {
                            variable: v,
                            operator: getDefaultOperator(v) as any,
                            value: Array.isArray(sig?.values) ? [] : ''
                        } as any;
                        if (sig && (sig.type ?? 'default') === 'attribute') {
                            (patch as any).type = 'attribute';
                            (patch as any).model = sig.model || '';
                        } else {
                            (patch as any).type = 'default';
                            delete (patch as any).model;
                        }
                        updateConditionAt(i, patch);
					}}
				/>
			</div>

			<!-- Operator Selector -->
			<div class="w-20">
				{#if true}
					{@const ops = getOperatorOptions(condition.variable)}
					{#if ops.length === 1}
						<Button.Root variant="outline" disabled class="w-full">{ops[0]}</Button.Root>
					{:else}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button.Root variant="outline" class="w-full">{condition.operator}</Button.Root>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content>
								{#each ops as op}
									<DropdownMenu.Item onSelect={() => updateConditionAt(i, { operator: op as any })}>
										{op}
									</DropdownMenu.Item>
								{/each}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				{/if}
			</div>

			<!-- Value Input -->
			<div class="flex-1">
				{#if true}
					{@const sig = getFieldSignature(condition.variable)}
                    {#if sig && Array.isArray(sig.values)}
						<MultiSelectWithSearch
							options={getValueOptions(condition.variable)}
							values={(condition.value as string[]) ?? []}
							onselect={(values) => updateConditionAt(i, { value: values })}
						/>
					{:else if sig?.values === 'date'}
						<DatePicker value={String(condition.value ?? '')}
									onchange={(v) => updateConditionAt(i, { value: v })}/>
					{:else if sig?.values === 'int' || sig?.values === 'float'}
						<Input type="number" step={sig.values === 'float' ? 'any' : '1'}
								value={String(condition.value ?? '')}
                                    oninput={(e: Event) => updateConditionAt(i, { value: (e.target as HTMLInputElement).value })}/>
					{:else}
						<Input type="text"
								value={String(condition.value ?? '')}
								placeholder="Enter value..."
								oninput={(e: Event) => updateConditionAt(i, { value: (e.target as HTMLInputElement).value })}/>
					{/if}
				{/if}
			</div>

			<!-- Remove Button -->
			<Button.Root variant="outline" size="sm" onclick={() => removeConditionAt(i)} class="p-2">
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
					{...{ onSelect: (v: string) => updateDraftField(v) }}
				/>
			</div>

			<!-- Operator Selector -->
			<div class="w-20">
				{#if draftRow.field}
					{@const ops = getOperatorOptions(draftRow.field)}
					{#if ops.length === 1}
						<Button.Root variant="outline" disabled class="w-full">{ops[0]}</Button.Root>
					{:else}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button.Root variant="outline" class="w-full">{draftRow.operator || '=='}</Button.Root>
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
					<Button.Root variant="outline" disabled class="w-full">--</Button.Root>
				{/if}
			</div>

			<!-- Value Input -->
			<div class="flex-1">
				{#if draftRow.field}
					{@const sig = getFieldSignature(draftRow.field)}
					{#if sig && Array.isArray(sig.values)}
						<MultiSelectWithSearch
							options={getValueOptions(draftRow.field)}
							values={(draftRow.value as string[]) ?? []}
							onselect={(values) => updateDraftValue(values)}
						/>
					{:else if sig?.values === 'date'}
						<DatePicker value={String(draftRow.value ?? '')}
								onchange={(v) => updateDraftValue(v)}/>
					{:else if sig?.values === 'int' || sig?.values === 'float'}
						<Input type="number" step={sig.values === 'float' ? 'any' : '1'}
								value={String(draftRow.value ?? '')}
                                onchange={(e: Event) => updateDraftValue((e.target as HTMLInputElement).value)}/>
					{:else}
						<Input value={String(draftRow.value ?? '')}
								placeholder="Enter value..."
                                onchange={(e: Event) => updateDraftValue((e.target as HTMLInputElement).value)}/>
					{/if}
				{:else}
					<Input type="text" disabled placeholder="Select field first..."/>
				{/if}
			</div>

			<!-- Cancel Button -->
			<Button.Root variant="outline" size="sm" onclick={cancelDraft} class="p-2">
				<Fa icon={faTrash} size="sm" />
			</Button.Root>
		</div>
	{/if}

	<!-- Add Filter Button -->
	<Button.Root variant="outline" onclick={startDraft} disabled={draftRow !== null} class="w-full">
		<Fa icon={faPlus} class="mr-2" size="sm" />
		Add Filter
	</Button.Root>
</div>

<style>
	

</style>