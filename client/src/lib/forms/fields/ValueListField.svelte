<!--
@component
A list of numbers or texts: one input per entry with × Remove, Add below. Entries keep their place while typing.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { tick } from "svelte";
    import { questionTitle, storedType } from "../fieldKind";
    import { formContext, type FieldProps } from "../formContext";
    import SchemaField from "../SchemaField.svelte";
    import { deref, pointer, type JSONSchema } from "../schemaType";

    let {
        node,
        path,
        depth,
        value,
        onchange,
        label,
        helperText,
        invalidText,
        readonly,
    }: FieldProps & { node: JSONSchema; path: string; depth: number } =
        $props();

    const ctx = formContext();
    const items = $derived(deref(node.items, ctx.root));
    const itemName = $derived(questionTitle(items, "Entry"));
    const entries = $derived(Array.isArray(value) ? (value as unknown[]) : []);
    const full = $derived(
        node.maxItems !== undefined && entries.length >= node.maxItems,
    );
    // An emptied entry keeps its place: "" for text, null for a number (which then asks for one).
    const empty = $derived(items && storedType(items) === "string" ? "" : null);
    let container = $state<HTMLElement | null>(null);

    async function remove(i: number) {
        onchange(entries.filter((_, j) => j !== i));
        await tick();
        container?.querySelector<HTMLElement>("[data-add]")?.focus();
    }
</script>

<fieldset bind:this={container} class="flex min-w-0 flex-col gap-2">
    <legend class="mb-2 text-label-01 text-text-secondary">{label}</legend>
    {#each entries as entry, i (i)}
        <SchemaField
            schema={node.items}
            value={entry}
            path={pointer(path, i)}
            name={itemName}
            title="{itemName} {i + 1}"
            depth={depth + 1}
            onremove={readonly ? undefined : () => remove(i)}
            onchange={(next) =>
                onchange(
                    entries.map((e, j) => (j === i ? (next ?? empty) : e)),
                )}
        />
    {/each}
    {#if !readonly}
        <Button
            data-add
            variant="outline"
            size="sm"
            class="self-start"
            disabled={full}
            onclick={() => onchange([...entries, empty])}>Add {itemName}</Button
        >
    {/if}
    {#if invalidText}
        <p class="text-helper-text-01 text-text-error">{invalidText}</p>
    {:else if full}
        <p class="text-helper-text-01 text-text-helper">
            Up to {node.maxItems}.
        </p>
    {:else if helperText}
        <p class="text-helper-text-01 text-text-helper">{helperText}</p>
    {/if}
</fieldset>
