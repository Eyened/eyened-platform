<!--
@component
An object's questions, in `_order` order.
-->
<script lang="ts">
    import { orderedKeys } from "./fieldKind";
    import { formContext } from "./formContext";
    import SchemaField from "./SchemaField.svelte";
    import { pointer, type JSONSchema } from "./schemaType";

    let {
        schema,
        value,
        path,
        depth,
        onchange,
    }: {
        schema: JSONSchema;
        value: unknown;
        path: string;
        depth: number;
        onchange: (next: Record<string, unknown>) => void;
    } = $props();

    const answers = $derived(
        typeof value === "object" && value !== null && !Array.isArray(value)
            ? (value as Record<string, unknown>)
            : {},
    );
    const ctx = formContext();
    const required = $derived(new Set(schema.required ?? []));

    // A cleared answer leaves the object, so the form says "not answered", not "empty".
    function set(key: string, next: unknown) {
        const copy = { ...answers };
        if (next === undefined) delete copy[key];
        else copy[key] = next;
        onchange(copy);
    }
</script>

<div class="flex flex-col gap-6">
    {#each orderedKeys(schema) as key (key)}
        <SchemaField
            schema={schema.properties?.[key]}
            value={answers[key]}
            path={pointer(path, key)}
            name={key}
            required={required.has(key) || ctx.requiredNow(pointer(path, key))}
            {depth}
            onchange={(next) => set(key, next)}
        />
    {/each}
</div>
