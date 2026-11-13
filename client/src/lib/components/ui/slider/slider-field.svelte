<script lang="ts">
    import { Input } from "$lib/components/ui/input/index.js";
    import { cn } from "$lib/utils.js";
    import Slider from "./slider.svelte";

    // Carbon default slider: a label, the track and a number field kept in sync. The field commits on Enter or blur.
    // Out of range auto-corrects to the nearest allowed value (Carbon slider); an unreadable entry reverts (S2 Number field).
    // ASSUMPTION: the field is 64 px wide.
    let {
        labelText,
        value,
        onchange,
        oncommit,
        min,
        max,
        step,
        decimals,
        unit,
    }: {
        labelText: string;
        value: number;
        onchange: (value: number) => void;
        oncommit?: () => void;
        min: number;
        max: number;
        step: number;
        decimals: number;
        /** Shown inside the field after the number, such as "%". */
        unit?: string;
    } = $props();

    const uid = $props.id();
    // Rounded to the shown decimals, so bits-ui does not rewrite a stored value such as 0.333. That is the step grid only when step is 10^-decimals.
    const onGrid = $derived(Number(value.toFixed(decimals)));
    const shown = $derived(value.toFixed(decimals));
    let text = $derived(shown);

    function commit() {
        // An untouched field keeps the stored value, even one with more decimals than shown.
        if (text === shown) return;
        const typed = Number.parseFloat(text);
        if (Number.isNaN(typed)) {
            text = shown;
            return;
        }
        const clamped = Math.min(max, Math.max(min, typed));
        const next = Number(
            (Math.round((clamped - min) / step) * step + min).toFixed(decimals),
        );
        text = next.toFixed(decimals);
        if (next === value) return;
        onchange(next);
        oncommit?.();
    }
</script>

<div class="flex w-full flex-col gap-2">
    <label for="{uid}-value" class="text-label-01 text-text-secondary"
        >{labelText}</label
    >
    <div class="flex items-center gap-4">
        <Slider
            class="min-w-0 flex-1"
            values={[onGrid]}
            onchange={(v) => onchange(v[0])}
            {oncommit}
            {min}
            {max}
            {step}
            labels={[labelText]}
            valueTexts={[`${shown}${unit ?? ""}`]}
        />
        <div class="relative w-16 shrink-0">
            <Input
                id="{uid}-value"
                type="number"
                {min}
                {max}
                {step}
                value={text}
                oninput={(e) => (text = e.currentTarget.value)}
                onchange={commit}
                onkeydown={(e) => {
                    if (e.key === "Enter") commit();
                }}
                class={cn(
                    "number-input-no-steppers px-2 text-end",
                    unit && "pr-6",
                )}
            />
            {#if unit}
                <span
                    aria-hidden="true"
                    class="pointer-events-none absolute inset-y-0 right-2 flex items-center text-body-compact-01 text-text-secondary"
                    >{unit}</span
                >
            {/if}
        </div>
    </div>
</div>
