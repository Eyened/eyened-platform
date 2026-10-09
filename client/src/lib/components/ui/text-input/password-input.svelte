<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";
    import type { TextInputProps } from "./text-input.svelte";

    // Carbon PasswordInput: TextInput plus a show/hide toggle (aria-label; no tooltip yet).
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        invalidText,
        id = uid,
        value = $bindable(""),
        ref = $bindable(null),
        "aria-describedby": describedBy,
        class: className,
        ...restProps
    }: TextInputProps = $props();

    let shown = $state(false);

    const errorId = $derived(`${id}-error`);
    const ariaDescribedBy = $derived(
        [invalidText ? errorId : undefined, describedBy]
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
        <button
            type="button"
            class="absolute inset-y-0 end-0 flex size-10 items-center justify-center hover:bg-background-hover"
            aria-label={shown ? "Hide password" : "Show password"}
            onclick={() => (shown = !shown)}
        >
            {#if shown}
                <ViewOff class="text-icon-primary" />
            {:else}
                <View class="text-icon-primary" />
            {/if}
        </button>
    </div>
    {#if invalidText}
        <Field.Error id={errorId}>{invalidText}</Field.Error>
    {/if}
</Field.Field>
