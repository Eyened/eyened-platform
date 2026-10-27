<script lang="ts" module>
    import type { HTMLInputAttributes } from "svelte/elements";

    export type NumberInputProps = Omit<
        HTMLInputAttributes,
        "type" | "value" | "files"
    > & {
        labelText: string;
        hideLabel?: boolean;
        id?: string;
        /** The raw text: "" when empty, never coerced to 0 (Carbon allowEmpty). */
        value?: string;
        ref?: HTMLInputElement | null;
        class?: string;
    };
</script>

<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";

    // Carbon NumberInput with hideSteppers and allowEmpty, over ui/input; values from @carbon/styles 1.117.0
    // number-input/_number-input.scss (150 px minimum width, no steppers).
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        hideLabel = false,
        id = uid,
        value = $bindable(""),
        ref = $bindable(null),
        class: className,
        ...restProps
    }: NumberInputProps = $props();
</script>

<Field.Field class={className}>
    <Field.Label for={id} class={hideLabel ? "sr-only" : undefined}
        >{labelText}</Field.Label
    >
    <!-- Not bind:value: Svelte binds a number input as a number, and clearing it would give null. -->
    <Input
        {...restProps}
        bind:ref
        {id}
        type="number"
        step="any"
        {value}
        oninput={(e) => (value = e.currentTarget.value)}
        class="number-input-no-steppers min-w-37.5"
    />
</Field.Field>
