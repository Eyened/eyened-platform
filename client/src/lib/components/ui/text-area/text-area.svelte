<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Textarea } from "$lib/components/ui/textarea/index.js";
    import { cn } from "$lib/utils.js";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";
    import type { Snippet } from "svelte";
    import type { HTMLTextareaAttributes } from "svelte/elements";

    // Carbon TextArea API over ui/textarea + ui/field; Carbon React's default of 4 rows.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        helperText,
        invalidText,
        invalidAction,
        resize = true,
        id = uid,
        value = $bindable(""),
        rows = 4,
        class: className,
        ...restProps
    }: Omit<HTMLTextareaAttributes, "value"> & {
        labelText: string;
        helperText?: string;
        /** Carbon's invalid state: the message replaces the helper text. */
        invalidText?: string;
        /** A control after the invalid message, such as Retry. */
        invalidAction?: Snippet;
        /** False hides the resize handle. */
        resize?: boolean;
        id?: string;
        value?: string;
        class?: string;
    } = $props();

    const errorId = $derived(`${id}-error`);
</script>

<Field.Field class={className}>
    <Field.Label for={id}>{labelText}</Field.Label>
    <div class="relative">
        <Textarea
            {...restProps}
            bind:value
            {id}
            {rows}
            aria-invalid={invalidText ? "true" : undefined}
            aria-describedby={invalidText
                ? errorId
                : helperText
                  ? `${id}-helper`
                  : undefined}
            class={cn(
                !resize && "resize-none",
                invalidText &&
                    "pe-10 not-focus:outline-2 not-focus:-outline-offset-2 not-focus:outline-support-error",
            )}
        />
        {#if invalidText}
            <WarningFilled
                class="absolute end-4 top-3 text-support-error"
                aria-hidden="true"
            />
        {/if}
    </div>
    {#if invalidText}
        <div class="flex items-center gap-2">
            <Field.Error id={errorId}>{invalidText}</Field.Error>
            {@render invalidAction?.()}
        </div>
    {:else if helperText}
        <p id="{id}-helper" class="text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</Field.Field>
