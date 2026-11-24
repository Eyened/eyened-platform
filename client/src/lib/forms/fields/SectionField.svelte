<!--
@component
An object question: a folding section, open at first; folded, it says how many answers it misses.
-->
<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { untrack } from "svelte";
    import FieldList from "../FieldList.svelte";
    import { formContext } from "../formContext";
    import type { JSONSchema } from "../schemaType";

    let {
        node,
        value,
        path,
        depth,
        label,
        invalidText,
        onchange,
    }: {
        node: JSONSchema;
        value: unknown;
        path: string;
        depth: number;
        label: string;
        invalidText?: string;
        onchange: (next: Record<string, unknown>) => void;
    } = $props();

    const ctx = formContext();
    let open = $state([untrack(() => path)]);
    const missing = $derived(ctx.missing(path));
    // The window title is h1, so top-level sections are h2.
    const level = $derived(Math.min(2 + depth, 6) as 2 | 3 | 4 | 5 | 6);

    // A notice link to this section or a question inside it unfolds the section.
    $effect(() => {
        const target = ctx.reveal?.path;
        if (target === undefined) return;
        const inside = target === path || target.startsWith(`${path}/`);
        if (inside && !untrack(() => open).includes(path)) {
            open = [...untrack(() => open), path];
        }
    });
</script>

<Accordion.Root bind:value={open}>
    <Accordion.Item value={path}>
        <Accordion.Trigger
            {level}
            summary={!open.includes(path) && missing > 0
                ? `${missing} not answered`
                : undefined}>{label}</Accordion.Trigger
        >
        <Accordion.Content>
            {#if invalidText}
                <p class="mb-4 text-helper-text-01 text-text-error">
                    {invalidText}
                </p>
            {/if}
            <FieldList
                schema={node}
                {value}
                {path}
                depth={depth + 1}
                {onchange}
            />
        </Accordion.Content>
    </Accordion.Item>
</Accordion.Root>
