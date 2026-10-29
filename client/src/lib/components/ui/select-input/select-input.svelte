<script lang="ts">
    import * as Field from "$lib/components/ui/field/index.js";
    import { NativeSelect } from "$lib/components/ui/native-select/index.js";
    import type { HTMLSelectAttributes } from "svelte/elements";

    // Carbon Select API over ui/native-select + ui/field. Named SelectInput because
    // bits-ui's ui/select is Carbon's Dropdown.
    // inline: Carbon's borderless select, for a table row on layer-01.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        hideLabel = false,
        inline = false,
        id = uid,
        value = $bindable(),
        class: className,
        children,
        ...restProps
    }: Omit<HTMLSelectAttributes, "value"> & {
        labelText: string;
        hideLabel?: boolean;
        inline?: boolean;
        id?: string;
        value?: string;
        class?: string;
    } = $props();
</script>

<Field.Field class={className}>
    <Field.Label for={id} class={hideLabel ? "sr-only" : undefined}
        >{labelText}</Field.Label
    >
    <NativeSelect
        {...restProps}
        bind:value
        {id}
        class={inline
            ? "border-b-transparent bg-transparent pl-2 hover:bg-field-hover-02 focus:bg-background [&+svg]:right-2"
            : undefined}
    >
        {@render children?.()}
    </NativeSelect>
</Field.Field>
