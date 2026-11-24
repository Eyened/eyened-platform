<script lang="ts">
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import { FieldLegend, FieldSet } from "$lib/components/ui/field/index.js";
    import { cn } from "$lib/utils.js";
    import type { FieldProps } from "../formContext";

    // Laid out like the radio button group: legend, boxes 8 px apart, then helper or error text (the error replaces the helper, Carbon).
    // Read-only boxes stay focusable and don't change.
    let {
        options,
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps & { options: readonly unknown[] } = $props();

    const uid = $props.id();
    const noteId = `${uid}-note`;
    const note = $derived(invalidText ?? helperText);
    const picked = $derived(Array.isArray(value) ? value : []);

    function toggle(option: unknown, on: boolean) {
        onchange(on ? [...picked, option] : picked.filter((v) => v !== option));
    }
</script>

<FieldSet class="min-w-0 gap-0" aria-describedby={note ? noteId : undefined}>
    <FieldLegend class="font-normal mb-2 text-label-01 text-text-secondary"
        >{label}</FieldLegend
    >
    <div class="flex flex-col gap-2">
        {#each options as option, i (i)}
            <span class="inline-flex items-center gap-2">
                <Checkbox
                    id="{uid}-{i}"
                    checked={picked.includes(option)}
                    {readonly}
                    onCheckedChange={(on) => toggle(option, on)}
                    class={cn(
                        readonly && "border-icon-disabled",
                        invalidText !== undefined && "border-support-error",
                    )}
                />
                <label
                    for="{uid}-{i}"
                    class={cn(
                        "text-body-compact-01 text-text-primary",
                        readonly ? "cursor-default" : "cursor-pointer",
                    )}>{String(option)}</label
                >
            </span>
        {/each}
    </div>
    {#if note}
        <p
            id={noteId}
            class={cn(
                "mt-2 text-helper-text-01",
                invalidText ? "text-text-error" : "text-text-helper",
            )}
        >
            {note}
        </p>
    {/if}
</FieldSet>
