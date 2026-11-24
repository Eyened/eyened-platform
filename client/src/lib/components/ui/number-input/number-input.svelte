<script lang="ts" module>
    import type { HTMLInputAttributes } from "svelte/elements";

    export type NumberInputProps = Omit<
        HTMLInputAttributes,
        "type" | "value" | "files" | "size"
    > & {
        labelText: string;
        hideLabel?: boolean;
        id?: string;
        /** The raw text: "" when empty, never coerced to 0 (Carbon allowEmpty). */
        value?: string;
        ref?: HTMLInputElement | null;
        /** Carbon sizes: md 40 px, sm 32 px. */
        size?: "sm" | "md";
        helperText?: string;
        /** Carbon invalid: a red outline, the warning icon and the error in place of the helper. */
        invalidText?: string;
        class?: string;
    };
</script>

<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";

    // Carbon NumberInput with hideSteppers and allowEmpty, over ui/input; values from @carbon/styles 1.117.0
    // number-input/_number-input.scss (150 px minimum width, no steppers).
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        hideLabel = false,
        id = uid,
        value = $bindable(""),
        ref = $bindable(null),
        size = "md",
        helperText,
        invalidText,
        class: className,
        ...restProps
    }: NumberInputProps = $props();

    const noteId = $derived(`${id}-note`);
    const note = $derived(invalidText ?? helperText);
</script>

<Field.Field class={className}>
    <Field.Label for={id} class={hideLabel ? "sr-only" : undefined}
        >{labelText}</Field.Label
    >
    <div class="relative">
        <!-- Not bind:value: Svelte binds a number input as a number, and clearing it would give null. -->
        <Input
            step="any"
            {...restProps}
            bind:ref
            {id}
            type="number"
            {value}
            oninput={(e) => (value = e.currentTarget.value)}
            aria-invalid={invalidText ? "true" : undefined}
            aria-describedby={note ? noteId : undefined}
            class="number-input-no-steppers min-w-37.5 {size === 'sm'
                ? 'h-8'
                : ''} {invalidText ? 'pe-10' : ''}"
        />
        {#if invalidText}
            <WarningFilled
                aria-hidden="true"
                class="absolute end-4 top-1/2 -translate-y-1/2 text-support-error"
            />
        {/if}
    </div>
    {#if invalidText}
        <Field.Error id={noteId}>{invalidText}</Field.Error>
    {:else if helperText}
        <p id={noteId} class="-mt-1 text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</Field.Field>
