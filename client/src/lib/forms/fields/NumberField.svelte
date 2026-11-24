<script lang="ts">
    import { NumberInput } from "$lib/components/ui/number-input/index.js";
    import { untrack } from "svelte";
    import type { FieldProps } from "../formContext";

    let {
        integer,
        errorsShown,
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps & { integer: boolean; errorsShown: boolean } = $props();

    function asText(v: unknown): string {
        return typeof v === "number" ? String(v) : "";
    }
    function parse(raw: string): number | undefined {
        return raw.trim() === "" ? undefined : Number(raw);
    }

    // The box's own text: "2.7" in a whole-number box stays on screen while no answer is saved.
    let text = $state(untrack(() => asText(value)));
    let draftError = $state<string | undefined>();

    // A change from outside (Clear, a reply) replaces the text, unless it already says that number or holds an unsaved decimal.
    $effect.pre(() => {
        const next = value;
        untrack(() => {
            if (draftError && next === undefined) return;
            if (parse(text) !== next) {
                text = asText(next);
                draftError = undefined;
            }
        });
    });

    function input(raw: string) {
        text = raw;
        const n = parse(raw);
        if (n !== undefined && integer && !Number.isInteger(n)) {
            // Nothing valid is on screen, so nothing stays saved.
            draftError = "Enter a whole number.";
            onchange(undefined);
        } else {
            draftError = undefined;
            onchange(n);
        }
    }
</script>

<NumberInput
    labelText={label}
    {helperText}
    {readonly}
    invalidText={(errorsShown ? draftError : undefined) ?? invalidText}
    bind:value={() => text, input}
/>
