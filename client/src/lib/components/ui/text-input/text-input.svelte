<script lang="ts" module>
    import type { HTMLInputAttributes } from "svelte/elements";

    export type TextInputProps = Omit<
        HTMLInputAttributes,
        "type" | "value" | "files"
    > & {
        labelText: string;
        hideLabel?: boolean;
        invalidText?: string;
        helperText?: string;
        id?: string;
        value?: string;
        ref?: HTMLInputElement | null;
        "aria-describedby"?: string;
        class?: string;
    };
</script>

<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";

    // Carbon TextInput API over ui/input + ui/field.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        hideLabel = false,
        invalidText,
        helperText,
        id = uid,
        value = $bindable(""),
        ref = $bindable(null),
        "aria-describedby": describedBy,
        class: className,
        ...restProps
    }: TextInputProps = $props();

    const errorId = $derived(`${id}-error`);
    const helperId = $derived(`${id}-helper`);
    // Carbon: the error replaces the helper text.
    const ariaDescribedBy = $derived(
        [invalidText ? errorId : helperText ? helperId : undefined, describedBy]
            .filter(Boolean)
            .join(" ") || undefined,
    );
</script>

<Field.Field class={className}>
    <Field.Label for={id} class={hideLabel ? "sr-only" : undefined}
        >{labelText}</Field.Label
    >
    <div class="relative">
        <Input
            {...restProps}
            bind:ref
            bind:value
            {id}
            type="text"
            aria-invalid={invalidText ? "true" : undefined}
            aria-describedby={ariaDescribedBy}
            class={invalidText ? "pe-10" : undefined}
        />
        {#if invalidText}
            <WarningFilled
                class="absolute end-4 top-1/2 -translate-y-1/2 text-support-error"
            />
        {/if}
    </div>
    {#if invalidText}
        <Field.Error id={errorId}>{invalidText}</Field.Error>
    {:else if helperText}
        <p id={helperId} class="text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</Field.Field>
