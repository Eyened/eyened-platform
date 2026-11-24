<!--
@component
A list of objects: a folding entry each ("Naevus 2"), Delete inside it, Add below.
-->
<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { tick, untrack } from "svelte";
    import FieldList from "../FieldList.svelte";
    import { questionTitle } from "../fieldKind";
    import { formContext, type FieldProps } from "../formContext";
    import {
        deref,
        isRecord,
        parsePointer,
        pointer,
        type JSONSchema,
    } from "../schemaType";

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
    const level = $derived(Math.min(2 + depth, 6) as 2 | 3 | 4 | 5 | 6);
    let open = $state(untrack(() => entries.map((_, i) => String(i))));
    let addButton = $state<HTMLElement | null>(null);

    // A notice link to a question inside an entry unfolds that entry.
    $effect(() => {
        const target = ctx.reveal?.path;
        if (!target?.startsWith(`${path}/`)) return;
        const entry = parsePointer(target)[parsePointer(path).length];
        if (entry !== undefined && !untrack(() => open).includes(entry)) {
            open = [...untrack(() => open), entry];
        }
    });

    function add() {
        open = [...open, String(entries.length)];
        onchange([...entries, {}]);
    }

    function drop(i: number) {
        open = open
            .filter((k) => k !== String(i))
            .map((k) => (Number(k) > i ? String(Number(k) - 1) : k));
        onchange(entries.filter((_, j) => j !== i));
    }

    // Carbon: an entry holding answers can't be recreated easily, so deleting it asks first; an empty one goes at once.
    let asking = $state<number | null>(null);
    let confirmOpen = $state(false);
    let deletedByModal = false;

    async function remove(i: number) {
        const entry = entries[i];
        if (isRecord(entry) && Object.keys(entry).length > 0) {
            asking = i;
            confirmOpen = true;
            return;
        }
        drop(i);
        await tick();
        addButton?.focus();
    }

    // The deleted entry's Delete button is gone, so focus goes to Add.
    function focusAddIfDeleted(event: Event) {
        if (!deletedByModal) return;
        deletedByModal = false;
        event.preventDefault();
        addButton?.focus();
    }
</script>

<div class="flex flex-col gap-2">
    <p class="text-label-01 text-text-secondary">{label}</p>
    <Accordion.Root bind:value={open}>
        {#each entries as entry, i (i)}
            <Accordion.Item value={String(i)}>
                <Accordion.Trigger {level}>{itemName} {i + 1}</Accordion.Trigger
                >
                <Accordion.Content>
                    {#if ctx.message(pointer(path, i))}
                        <p class="mb-4 text-helper-text-01 text-text-error">
                            {ctx.message(pointer(path, i))}
                        </p>
                    {/if}
                    {#if items}
                        <FieldList
                            schema={items}
                            value={entry}
                            path={pointer(path, i)}
                            depth={depth + 1}
                            onchange={(next) =>
                                onchange(
                                    entries.map((e, j) => (j === i ? next : e)),
                                )}
                        />
                    {/if}
                    {#if !readonly}
                        <Button
                            variant="danger-ghost"
                            size="sm"
                            class="mt-4"
                            onclick={() => remove(i)}
                            >Delete {itemName} {i + 1}<TrashCan /></Button
                        >
                    {/if}
                </Accordion.Content>
            </Accordion.Item>
        {/each}
    </Accordion.Root>
    {#if !readonly}
        <Button
            bind:ref={addButton}
            variant="outline"
            size="sm"
            class="self-start"
            disabled={full}
            onclick={add}>Add {itemName}</Button
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
</div>

<Modal
    bind:open={confirmOpen}
    danger
    size="xs"
    modalHeading="Delete {itemName} {(asking ?? 0) + 1}"
    modalLabel={label}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="{itemName} could not be deleted"
    onsubmit={async () => {
        if (asking === null) return;
        deletedByModal = true;
        drop(asking);
    }}
    onCloseAutoFocus={focusAddIfDeleted}
>
    <p>Deletes its answers. This can't be undone.</p>
</Modal>
