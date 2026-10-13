<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { Textarea } from "$lib/components/ui/textarea/index.js";
    import type { HTMLTextareaAttributes } from "svelte/elements";

    // Carbon TextArea API over ui/textarea + ui/field; Carbon React's default of 4 rows.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        id = uid,
        value = $bindable(""),
        rows = 4,
        class: className,
        ...restProps
    }: Omit<HTMLTextareaAttributes, "value"> & {
        labelText: string;
        id?: string;
        value?: string;
        class?: string;
    } = $props();
</script>

<Field.Field class={className}>
    <Field.Label for={id}>{labelText}</Field.Label>
    <Textarea {...restProps} bind:value {id} {rows} />
</Field.Field>
