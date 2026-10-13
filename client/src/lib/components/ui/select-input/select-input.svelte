<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { NativeSelect } from "$lib/components/ui/native-select/index.js";
    import type { HTMLSelectAttributes } from "svelte/elements";

    // Carbon Select API over ui/native-select + ui/field. Named SelectInput because
    // bits-ui's ui/select is Carbon's Dropdown.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        id = uid,
        value = $bindable(),
        class: className,
        children,
        ...restProps
    }: Omit<HTMLSelectAttributes, "value"> & {
        labelText: string;
        id?: string;
        value?: string;
        class?: string;
    } = $props();
</script>

<Field.Field class={className}>
    <Field.Label for={id}>{labelText}</Field.Label>
    <NativeSelect {...restProps} bind:value {id}>
        {@render children?.()}
    </NativeSelect>
</Field.Field>
