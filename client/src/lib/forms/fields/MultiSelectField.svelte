<script lang="ts">
    import { MultiSelect } from "$lib/components/ui/multi-select/index.js";
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

    const picked = $derived(Array.isArray(value) ? value : []);
    // In pick order; a value saved twice shows once.
    const indices = $derived([
        ...new Set(
            picked.flatMap((v) => {
                const i = options.indexOf(v);
                return i < 0 ? [] : [String(i)];
            }),
        ),
    ]);
</script>

{#if readonly}
    <TextInput
        labelText={label}
        {helperText}
        readonly
        value={picked.map(String).join(", ")}
    />
{:else}
    <MultiSelect
        titleText={label}
        options={options.map((option, i) => ({
            value: String(i),
            label: String(option),
        }))}
        bind:values={
            () => indices,
            (next) => onchange(next.map((i) => options[Number(i)]))
        }
        {helperText}
        {invalidText}
    />
{/if}
