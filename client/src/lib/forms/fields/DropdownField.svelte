<script lang="ts">
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import type { FieldProps } from "../formContext";

    let {
        options,
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps & { options: readonly unknown[] } = $props();

    const index = $derived(options.findIndex((option) => option === value));
</script>

{#if readonly}
    <!-- A read-only list has no menu to open, so it reads as a read-only field. -->
    <TextInput
        labelText={label}
        {helperText}
        readonly
        value={index < 0 ? "" : String(options[index])}
    />
{:else}
    <Dropdown
        labelText={label}
        size="md"
        placeholder="Choose an option"
        items={options.map((option, i) => ({
            id: String(i),
            text: String(option),
        }))}
        selectedId={index < 0 ? undefined : String(index)}
        {helperText}
        {invalidText}
        onselect={(id) => onchange(options[Number(id)])}
    />
{/if}
