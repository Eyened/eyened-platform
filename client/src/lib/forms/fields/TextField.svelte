<script lang="ts">
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import type { FieldProps } from "../formContext";

    let {
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps = $props();
</script>

<TextInput
    labelText={label}
    {helperText}
    {invalidText}
    {readonly}
    bind:value={
        () => (typeof value === "string" ? value : ""),
        (next) => onchange(next === "" ? undefined : next)
    }
/>
