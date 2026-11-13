<!--
@component
A number field that applies a positive, in-range value on Enter, blur or a step, and otherwise puts the last value back.
-->
<script lang="ts">
    import { NumberInput } from "$lib/components/ui/number-input/index.js";

    let {
        labelText,
        value,
        step,
        min,
        max,
        oncommit,
    }: {
        labelText: string;
        value: number;
        step: number;
        min?: number;
        max?: number;
        oncommit: (value: number) => void;
    } = $props();

    function commit(input: HTMLInputElement) {
        const next = Number(input.value);
        const valid =
            input.value.trim() !== "" &&
            Number.isFinite(next) &&
            next > 0 &&
            (min === undefined || next >= min) &&
            (max === undefined || next <= max);
        if (valid) oncommit(next);
        else input.value = String(value);
    }
</script>

<NumberInput
    {labelText}
    value={String(value)}
    step={String(step)}
    min={min === undefined ? undefined : String(min)}
    max={max === undefined ? undefined : String(max)}
    onchange={(e) => commit(e.currentTarget)}
    onkeydown={(e) => {
        if (e.key === "Enter") commit(e.currentTarget);
    }}
/>
