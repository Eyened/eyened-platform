<script lang="ts">
    import { RadioButtonGroup } from "$lib/components/ui/radio-button/index.js";
    import type { FieldProps } from "../formContext";

    let {
        options,
        labels,
        vertical,
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps & {
        options: readonly unknown[];
        /** Words per option when they differ from the stored value (Yes / No). */
        labels?: readonly string[];
        vertical: boolean;
    } = $props();

    // Options by position, so number and boolean answers keep their type.
    const items = $derived(
        options.map((option, i) => ({
            value: String(i),
            labelText: labels?.[i] ?? String(option),
        })),
    );
    const index = $derived(options.findIndex((option) => option === value));
</script>

<RadioButtonGroup
    legendText={label}
    {items}
    orientation={vertical ? "vertical" : "horizontal"}
    {helperText}
    {invalidText}
    {readonly}
    bind:selected={
        () => (index < 0 ? undefined : String(index)),
        (i) => onchange(options[Number(i)])
    }
/>
