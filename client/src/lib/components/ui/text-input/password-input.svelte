<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";
    import type { TextInputProps } from "./text-input.svelte";

    // Carbon PasswordInput: TextInput plus a show/hide icon button with tooltip.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        invalidText,
        helperText,
        id = uid,
        value = $bindable(""),
        ref = $bindable(null),
        "aria-describedby": describedBy,
        class: className,
        ...restProps
    }: TextInputProps = $props();

    let shown = $state(false);

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
    <Field.Label for={id}>{labelText}</Field.Label>
    <div class="relative">
        <Input
            {...restProps}
            bind:ref
            bind:value
            {id}
            type={shown ? "text" : "password"}
            aria-invalid={invalidText ? "true" : undefined}
            aria-describedby={ariaDescribedBy}
            class="pe-16"
        />
        {#if invalidText}
            <WarningFilled
                class="absolute end-10 top-1/2 -translate-y-1/2 text-support-error"
            />
        {/if}
        <div class="absolute inset-y-0 end-0">
            <IconButton
                label={shown ? "Hide password" : "Show password"}
                onclick={() => (shown = !shown)}
            >
                {#if shown}
                    <ViewOff />
                {:else}
                    <View />
                {/if}
            </IconButton>
        </div>
    </div>
    {#if invalidText}
        <Field.Error id={errorId}>{invalidText}</Field.Error>
    {:else if helperText}
        <p id={helperId} class="text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</Field.Field>
